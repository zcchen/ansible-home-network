#!/usr/bin/env sh

XRAY_GEODATA_GEOSITE_FILE_LINK="https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geosite.dat"
XRAY_GEODATA_GEOIP_FILE_LINK="https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geoip.dat"
XRAY_GEODATA_GEOSITE_SHA256SUM_LINK="https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geosite.dat.sha256sum"
XRAY_GEODATA_GEOIP_SHA256SUM_LINK="https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geoip.dat.sha256sum"


# the vars to be changed at parsing stage

# for bash: -e exits on error, -u errors on undefined variables, -x prints commands before execution, and -o (for option) pipefail exits on command pipe failures.
#set -euxo pipefail
# for sh: -e exits on error, -u errors on undefined variables
#set -eu

# default vars
DEFAULT_GEODATA_FOLDER=/usr/share/xray

# script vars will be used later
VAR__XRAY_GEODATA_FOLDER="${DEFAULT_GEODATA_FOLDER}"
VAR__IS_VERBOSE=false
VAR__EXEC_CMD_AFTER_UPDATE=""

do__print_help () {
  echo "$0 [-v] [-d <geo-data-dir>] [exec-cmd-after-geodate-updated ...]"
  echo "    -v, verbose flag.."
  echo "    -d <geo-data-dir>, the folder to save the geodata, default is <${DEFAULT_GEODATA_FOLDER}>"
  echo "    [exec-cmd-after-geodate-updated], execute commands after geodata updated.."
}

log_print() {   # level: 0-4, error; 5-9, info; >=10: debug
  local level=$1
  local msg=$2
  if [ ${level} -ge 0 -a ${level} -lt 5 ]; then
    echo "$(date +'%Y-%m-%d %H:%M:%S') [ERROR] ${msg}"
  elif [ ${level} -ge 5 -a ${level} -lt 9 ]; then
    echo "$(date +'%Y-%m-%d %H:%M:%S') [INFO]  ${msg}"
  else
    if [ ${VAR__IS_VERBOSE} = true ]; then
      echo "$(date +'%Y-%m-%d %H:%M:%S') [DEBUG] ${msg}"
    fi
  fi
}

do__parse_opts () {
  while getopts ":hlvd:e:" opt; do
    case ${opt} in
      h)
        do__print_help
        exit 0
        ;;
      d)
        VAR__XRAY_GEODATA_FOLDER="${OPTARG}"
        ;;
      v)
        VAR__IS_VERBOSE=true
        ;;
      :)
        echo ">>> Option -${OPTARG} requires an argument."
        do__print_help
        exit 1
        ;;
      ?)
        echo ">>> Invalid option: -${OPTARG}."
        do__print_help
        exit 1
        ;;
    esac
  done
  shift $(expr $OPTIND - 1)
  VAR__EXEC_CMD_AFTER_UPDATE="$@"
}

do__create_folder_target() {
  if [ -z "$(ls -A ${VAR__XRAY_GEODATA_FOLDER} 2>/dev/null)" ]; then
    log_print 10 "<${VAR__XRAY_GEODATA_FOLDER}> does NOT exist now."
    log_print 10 "Creating the folders: <${VAR__XRAY_GEODATA_FOLDER}>."
    mkdir -p "${VAR__XRAY_GEODATA_FOLDER}"
    log_print 10 "Folder <${VAR__XRAY_GEODATA_FOLDER}> is created."
  fi
}

VAR__TMP_DIR=`mktemp -d`
do__clean_tmpdir() {
  if [ -d ${VAR__TMP_DIR} ]; then
    log_print 10 "Removing tmp dir <${VAR__TMP_DIR}>."
    rm -rf ${VAR__TMP_DIR}
    log_print 10 "Tmp dir <${VAR__TMP_DIR}> is removed."
  fi
}
trap do__clean_tmpdir EXIT

do__check_hash() {
  local checksum_cmd="$1"
  local filename="$2"
  local checksum_expected="$3"
  local checksum_calc=""
  if [ ! -f "${filename}" ]; then # no file
    if [ ${VAR__IS_VERBOSE} = true ]; then
      log_print 0 "File <${filename}> is missing while trying toe check file hash."
    fi
    return 2
  fi
  checksum_calc=$(${checksum_cmd} "${filename}" | awk '{print $1}')
  if [ "${checksum_calc}" = "${checksum_expected}" ]; then
    log_print 10 "<${filename}>'s ${checksum_cmd} is <${checksum_calc}>."
    log_print 10 "    as expected!"
    return 0
  else
    log_print 10 "<${filename}>'s ${checksum_cmd} is <${checksum_calc}>."
    log_print 10 "    but the expection is <${checksum_expected}>."
    return 1
  fi
}

do__download_and_check() {
  local url_file="$1"
  local url_checksum="$2"
  local output_file="$3"

  log_print 10 "Trying to get file from <${url_file}>."
  log_print 10 "Expecting checksum of this file is from <${url_checksum}>."
  log_print 10 "Download output is <${output_file}>."

  local retry_max=10
  local retry_count=0
  log_print 10 "Downloading..."
  while [ ${retry_count} -lt ${retry_max} ]; do
    #wget --tries 100 --read-timeout 20 "${url_file}" -O "${output_file}"
    curl -qfsS -w 'Got %{size_download} bytes from <%{url}>.\n' -L --retry 5 --max-time 60 --keepalive-time 10 "${url_file}" -o "${output_file}"
    if [ $? -eq 0 ]; then
      local expected_checksum="$(curl -s -L "${url_checksum}" | awk '{print $1}')"
      do__check_hash "sha256sum" "${output_file}" "${expected_checksum}"
      if [ $? -eq 0 ]; then
        log_print 10 "Succeed to get file from <${url_file}>."
        return 0
      else
        log_print 0 "Checksum Failed. Retrying <${retry_count}> to download file <${url_file}>."
        retry_count=$((${retry_count} + 1))
      fi
    else
      log_print 0 "Download Failed. Retrying <${retry_count}> to download file <${url_file}>."
      retry_count=$((${retry_count} + 1))
    fi
  done

  return 1
}

main() {
  do__parse_opts $@
  log_print 5 "Start to update xray geodate..."
  do__create_folder_target

  local flag_is_updated=false

  local url_file=""
  local url_checksum=""
  for f in geoip.dat geosite.dat; do
    if [ ${f} = "geoip.dat" ]; then
      url_file="${XRAY_GEODATA_GEOIP_FILE_LINK}"
      url_checksum="${XRAY_GEODATA_GEOIP_SHA256SUM_LINK}"
    elif [ ${f} = "geosite.dat" ]; then
      url_file="${XRAY_GEODATA_GEOSITE_FILE_LINK}"
      url_checksum="${XRAY_GEODATA_GEOSITE_SHA256SUM_LINK}"
    else
      log_print 0 "Unexpected error."
      return 3
    fi

    local expected_checksum="$(curl -s -L "${url_checksum}" | awk '{print $1}')"
    do__check_hash "sha256sum" "${VAR__XRAY_GEODATA_FOLDER}/${f}" "${expected_checksum}"
    if [ $? -eq 0 ]; then
      # file already updated to latest, skip.
      continue
    else
      # update file
      do__download_and_check "${url_file}" "${url_checksum}" "${VAR__TMP_DIR}/${f}"
      if [ $? -eq 0 ]; then
        log_print 10 "Updating <${f}> to <${VAR__XRAY_GEODATA_FOLDER}>"
        cp ${cp_flags} "${VAR__TMP_DIR}/${f}" "${VAR__XRAY_GEODATA_FOLDER}/${f}"
        flag_is_updated=true
      else
        log_print 0 "Failed to download ${f}."
        return 4
      fi
    fi
  done

  if [ -n "${VAR__EXEC_CMD_AFTER_UPDATE}" -a ${flag_is_updated} = "true" ]; then
    log_print 5 "geodata updated, executing post-updated command..."
    log_print 10 ">>> ${VAR__EXEC_CMD_AFTER_UPDATE}"
    sh -c "${VAR__EXEC_CMD_AFTER_UPDATE}"
    if [ $? -ne 0 ]; then
        log_print 0 "FAILED to execute the post-updated command <${VAR__EXEC_CMD_AFTER_UPDATE}>."
        return 5
    else
        log_print 5 "Succeed to execute the post-updated command."
    fi
  fi

  log_print 5 "xray geodate are updated..."
  return 0
}

main $@
