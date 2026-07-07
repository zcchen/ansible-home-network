#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: my_test

short_description: This is my test module

# If this is part of a collection, you need to use semantic versioning,
# i.e. the version is of the form "2.5.0" and not "2.4".
version_added: "1.0.0"

description: This is my longer description explaining my test module.

options:
    name:
        description: This is the message to send to the test module.
        required: true
        type: str
    new:
        description:
            - Control to demo if the result of this module is changed or not.
            - Parameter description can be a list as well.
        required: false
        type: bool
# Specify this value according to your collection
# in format of namespace.collection.doc_fragment_name
# extends_documentation_fragment:
#     - my_namespace.my_collection.my_doc_fragment_name

author:
    - Your Name (@yourGitHubHandle)
'''

EXAMPLES = r'''
# Pass in a message
- name: Test with a message
  my_namespace.my_collection.my_test:
    name: hello world

# pass in a message and have changed true
- name: Test with a message and changed output
  my_namespace.my_collection.my_test:
    name: hello world
    new: true

# fail the module
- name: Test failure of the module
  my_namespace.my_collection.my_test:
    name: fail me
'''

RETURN = r'''
# These are examples of possible return values, and in general should use other names for return values.
original_message:
    description: The original name param that was passed in.
    type: str
    returned: always
    sample: 'hello world'
message:
    description: The output message that the test module generates.
    type: str
    returned: always
    sample: 'goodbye'
'''

from ansible.module_utils.basic import AnsibleModule
import traceback
import re
import string, random

class UciHandler:

    def __init__(self, m):
        self.__m = m
        self.__orig_data = self._show_config()
        self.__debug_msglist = []

    def __append_debug(self, s):
        return self.__debug_msglist.append(s)

    def get_debug_msglist(self):
        return self.__debug_msglist

    def _exec(self, command, options=[], arguments=[], raise_when_failed=False, err_msg_prefix="",
              use_python_splitlines=True):
        ret = { 'success': False,
                'cmd': '',
                'stdout_lines': [],
                'stderr_lines': [],
        }
        cmd = ['uci']
        if options:
            cmd += options
        cmd += [command]
        if arguments:
            cmd += arguments
        ret['cmd'] = " ".join(cmd)
        rc, out, err = self.__m.run_command(ret['cmd'])
        if raise_when_failed and rc:
            s = "{}".format(err_msg_prefix + '\n' if err_msg_prefix else "") + \
                    "> exec command:\n{}".format(cmd) + \
                    "\n> exec stdout:\n{}".format(out) + \
                    "\n> exec stderr:\n{}".format(err)
            raise RuntimeError(s)
        if not rc:
            ret['success'] = True
        tmp_s = ""
        if use_python_splitlines:
            ret['stdout_lines'] = out.splitlines()
            ret['stderr_lines'] = err.splitlines()
        else:
            outlines = out.splitlines()
            for l in outlines:
                if "=" in l:
                    if "=" in tmp_s:
                        ret['stdout_lines'].append(tmp_s)
                    tmp_s = l
                else:
                    tmp_s += l
            ret['stderr_lines'] = err.splitlines()
        return ret

    def _show_config(self, config=''):
        exec_ret = self._exec('show', options=['-X'], arguments=[f'{config}'],
                raise_when_failed=True,
                err_msg_prefix=f'failed when trying to show uci config <{config}>',
                use_python_splitlines=False
        )
        ret = {}
        for l in exec_ret['stdout_lines']:
            equal_index = l.index('=')
            keys = l[:equal_index]
            value = l[equal_index + 1:]
            keys_list = keys.split('.')
            if len(keys_list) == 2:     # generate the section part
                conf, section = keys_list
                if conf not in ret.keys():
                    ret[conf] = {}
                if section not in ret[conf].keys():
                    ret[conf][section] = {
                        'type' : value,
                        'options': {
                        }
                    }
            elif len(keys_list) == 3:   # generate the option part
                conf, section, option = keys_list
                if not conf in ret.keys():
                    s_err = '\n'.join(exec_ret['stderr_lines'])
                    s = f"<{conf}> is not in current uci configs. stderr: <{s_err}>"
                    raise RuntimeError(s)
                if not section in ret[conf].keys():
                    s_err = '\n'.join(exec_ret['stderr_lines'])
                    s = f"<{section}> is missing in config <{conf}>, stderr: <{s_err}>."
                    raise RuntimeError(s)
                # TODO: use config files to ensure the option is list type.
                val_pattern = r"^'([^']+)'$"
                if re.match(val_pattern, value):  # the value is simple option
                    ret[conf][section]['options'][option] = re.sub(val_pattern, r"\1", value)
                else:   # the value should be options
                    v = value.split(' ')
                    ret[conf][section]['options'][option] = \
                        [re.sub(val_pattern, r"\1", i) for i in v]
            else:   # raise the runtime error
                s_err = '\n'.join(exec_ret['stderr_lines'])
                s = f"failed to parse the line <{l}>, stderr: <{s_err}>"
                raise RuntimeError(s)
        return ret

    def _show_changes(self):
        exec_ret = self._exec('changes', raise_when_failed=True,
                err_msg_prefix='failed when trying to show uci changes'
        )
        ret = {'create_or_update': {}, 'delete': {}}
        self.__append_debug("show changes:")
        for l in exec_ret['stdout_lines']:
            self.__append_debug(l)
            if l.startswith('-'):
                ret_key = 'delete'
                line = l[1:]
            elif l.startswith('+'):
                ret_key = 'create_or_update'
                line = l[1:]
            else:
                ret_key = 'create_or_update'
                line = l
            def set_ret_value(keys_with_dots, value=None):
                keys_list = keys_with_dots.split('.')
                if len(keys_list) == 2:
                    conf, section = keys_list
                elif len(keys_list) == 3:
                    conf, section, option = keys_list
                else:   # raise the runtime error
                    s_err = '\n'.join(exec_ret['stderr_lines'])
                    s = f"failed to parse the line <{l}>, stderr: <{s_err}>"
                    raise RuntimeError(s)
                if not conf in ret[ret_key].keys():
                    ret[ret_key][conf] = {}
                if not section in ret[ret_key][conf].keys():
                    ret[ret_key][conf][section] = {}
                if value and len(keys_list) == 3:
                    if type(value) is str:
                        ret[ret_key][conf][section][option] = value
                    elif type(value) is list:
                        if not option in ret[ret_key][conf][section].keys():
                            ret[ret_key][conf][section][option] = []
                        ret[ret_key][conf][section][option] += value
            equal_index = line.find('=')
            if equal_index < 0:
                set_ret_value(line)
            else:
                if line[equal_index - 1] == '-' or line[equal_index - 1] == '+':
                    option_type = 'list'
                    set_ret_value(line[: equal_index - 1], [line[equal_index + 1:]])
                else:
                    option_type = 'str'
                    set_ret_value(line[: equal_index], line[equal_index + 1:])
        return ret

    def to_ansible(self, changed=False, failed=True, msg='', uci={}):
        ret = {
            "changed": changed,
            "failed": failed,
            'msg': msg,
            'uci': uci,
        }
        return ret

    def commit(self, config):
        ret = self._show_changes()
        self._exec('commit', options=[], arguments=[f'{config}'],
                   raise_when_failed=True,
                   err_msg_prefix="Failed to commit when trying to create section."
        )
        return ret

    def revert(self, config):
        return self._exec('revert', options=[], arguments=[f'{config}'])

    def show(self, config=""):
        ret = {}
        if not config:
            ret = self.__orig_data
        else:
            if config in self.__orig_data.keys():
                ret = {config: self.__orig_data[config]}
            else:
                ret = {}
        return ret

    def create_section(self, config, section_type, skip_if_existed=True, section_name="", options={}):
        if config in self.__orig_data.keys() \
                and section_name and section_name in self.__orig_data[config].keys():
            if skip_if_existed:
                return
            s = f'<{section_name}> is already existed in config <{config}>'
            raise RuntimeError(s)
        if section_name and not re.match(r'^[0-9a-zA-Z_]+$', section_name):
            s = f"<{section_name}> is invalid, only alpha, number and '_' are available."
            raise RuntimeError(s)
        r = self._exec("add", arguments=[f'{config}', f"{section_type}"], raise_when_failed=True,
                err_msg_prefix=f'failed to add section-type ({section_type}) to config <{config}>.'
        )
        s_name = r['stdout_lines'][0]
        for opt_name, opt_value in options.items():
            if type(opt_value) is str or type(opt_value) is int or type(opt_value) is float:
                self._exec('set', arguments=[f"{config}.{s_name}.{opt_name}='{opt_value}'"],
                        raise_when_failed=True,
                        err_msg_prefix=f'failed to set <{config}.{s_name}.{opt_name}> as <{opt_value}>.'
                )
            elif type(opt_value) is list:
                for v in opt_value:
                    self._exec('add_list', arguments=[f"{config}.{s_name}.{opt_name}='{v}'"],
                            raise_when_failed=True,
                            err_msg_prefix=f'failed to add_list <{config}.{s_name}.{opt_name}> with <{v}>.'
                    )
            else:
                raise RuntimeError(f"Unsupport option data type: {type(opt_value)}.")
        if section_name:
            self._exec("rename", arguments=[f"{config}.{s_name}='{section_name}'"],
                    raise_when_failed=True,
                    err_msg_prefix=f'failed to name the internal section <{s_name}> to <{section_name}>.'
            )

    def delete(self, config, section_name, options=[], list_options={}):
        if config not in self.__orig_data.keys():
            s = f'config <{config}> is NOT existed'
            raise RuntimeError(s)
        if section_name not in self.__orig_data[config].keys():
            s = f'section <{section_name}> is NOT existed in config <{config}>'
            raise RuntimeError(s)
        if not options and not list_options:
            self._exec("delete", arguments=[f'{config}.{section_name}'],
                    raise_when_failed=True,
                    err_msg_prefix=f'failed to delete section <{config}.{section_name}>.'
            )
        else:
            for option in options:
                self._exec("delete", arguments=[f'{config}.{section_name}.{option}'],
                        raise_when_failed=True,
                        err_msg_prefix=f'failed to delete option <{config}.{section_name}.{option}>.'
                )
            for opt_key, opt_value_list in list_options.items():
                if type(opt_value_list) is not list:
                    raise TypeError(f"opt_value must be type list: <{opt_value_list}>.")
                for v in opt_value_list:
                    self._exec("del_list",
                            arguments=[f"{config}.{section_name}.{opt_key}='{v}'"],
                            raise_when_failed=True,
                            err_msg_prefix=f"failed to del_list option <{config}.{section_name}.{opt_key}='{v}'>"
                    )

    def find_sections(self, config, section_type='', opt_cond='and', options={}):
        # return section name if found, else return None
        # FIXME: currently, only matched key-values are supported
        ret = []
        if config not in self.__orig_data.keys():   # config is NOT existed.
            return ret
        if opt_cond not in ['and', 'or']:
            raise ValueError("opt_cond should ONLY be 'and' or 'or'.")
        if not options and not section_type:
            raise ValueError("No available options nor section type. Both are EMPTY.")
        for section_name, value in self.__orig_data[config].items():
            if section_type:
                if value['type'] != section_type:   # skip the unmatced section type.
                    continue
                else:
                    if not options: # no options, no need to be continued.
                        ret.append(section_name)
                        continue
            found_unmatched_at_and_cond = True
            for opt_name, opt_value in options.items():
                if opt_name in value['options'].keys() and opt_value == value['options'][opt_name]:
                    if opt_cond == 'and':
                        self.__append_debug(f"found opt <{opt_name}> matching value <{opt_value}> in 'and' cond.")
                        found_unmatched_at_and_cond = False
                        continue
                    if opt_cond == 'or':
                        self.__append_debug(f"found opt <{opt_name}> matching value <{opt_value}> in 'or' cond.")
                        ret.append(section_name)
                        break;
                else:
                    found_unmatched_at_and_cond = True
                    break;
            self.__append_debug(f"found_unmatched_at_and_cond: <{found_unmatched_at_and_cond}>.")
            if not found_unmatched_at_and_cond:
                ret.append(section_name)
        self.__append_debug(f"ret: {ret}.")
        return {'found': ret}

    def update(self, config, section_name, options={}):
        if config not in self.__orig_data.keys():
            s = f'config <{config}> is NOT existed'
            raise RuntimeError(s)
        if section_name not in self.__orig_data[config].keys():
            s = f'section <{section_name}> is NOT existed in config <{config}>, only has {self.__orig_data[config].keys()}'
            raise RuntimeError(s)
        for opt_key, opt_value in options.items():
            if type(opt_value) is str or type(opt_value) is int or type(opt_value) is float:
                self._exec("set",
                        arguments=[f"{config}.{section_name}.{opt_key}='{opt_value}'"],
                        raise_when_failed=True,
                        err_msg_prefix=f"failed to set option <{config}.{section_name}.{opt_key}='{opt_value}'>"
                )   # this also handles the situation which the option should be added before updating.
            elif type(opt_value) is list:
                curr_values = []
                exec_ret = self._exec('get', options=[],
                        arguments=[f'{config}.{section_name}.{opt_key}'],
                        raise_when_failed=False,
                        err_msg_prefix=f'failed to get option <{config}.{section_name}.{opt_key}> before reset it'
                )
                if exec_ret['stdout_lines']:
                    l = exec_ret['stdout_lines'][0]
                    curr_values = l.split(' ')
                index_changing = len(curr_values)
                for i in range(len(curr_values)):
                    if i >= len(opt_value): # all values over index i (including) are changing
                        index_changing = i
                        break
                    if str(curr_values[i]) != str(opt_value[i]): # index i changed
                        index_changing = i
                        break
                actions_by_del_and_add = (len(curr_values) - index_changing) + (len(opt_value) - index_changing)
                actions_by_clear_then_add = 1 + len(opt_value)
                if actions_by_del_and_add < actions_by_clear_then_add:
                    for v in curr_values[index_changing:]:
                        exec_ret = self._exec('del_list', options=[],
                                arguments=[f"{config}.{section_name}.{opt_key}='{v}'"],
                                raise_when_failed=True,
                                err_msg_prefix=f"failed to del_list to <{config}.{section_name}.{opt_key}='{v}'>"
                        )
                    for v in opt_value[index_changing:]:
                        exec_ret = self._exec('add_list', options=[],
                                arguments=[f"{config}.{section_name}.{opt_key}='{v}'"],
                                raise_when_failed=True,
                                err_msg_prefix=f"failed to add_list to <{config}.{section_name}.{opt_key}='{v}'>"
                        )
                else:
                    exec_ret = self._exec('delete', options=[],
                            arguments=[f'{config}.{section_name}.{opt_key}'],
                            raise_when_failed=False,
                            err_msg_prefix=f'failed to del option <{config}.{section_name}.{opt_key}> before reset it'
                    )
                    for v in opt_value:
                        exec_ret = self._exec('add_list', options=[],
                                arguments=[f"{config}.{section_name}.{opt_key}='{v}'"],
                                raise_when_failed=True,
                                err_msg_prefix=f"failed to add_list to <{config}.{section_name}.{opt_key}='{v}'>"
                        )
            else:
                raise RuntimeError(f"Unsupport type <{type(opt_value)}>.")


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        config = {
            "type": 'str',
            'default': ''
        },
        command = {
            "type": 'str',
            'required': True,
            'choices': ['show', 'create', 'delete', 'update', 'find_sections', "commit", "revert", "reset"]
        },
        skip_if_existed = { # valid when command is create
            "default": True,
            "type": 'bool',
        },
        sections = {
            "type": 'list',
            'elements': 'dict',
            # 'options': dict(
                # type='dict',
                # options={
                    # 'name': {
                        # "type": 'str',
                        # 'default': '',
                    # },
                    # 'type': {
                        # "type": 'str',
                        # 'required': True,
                    # },
                    # 'options': {
                        # 'type': 'dict',
                    # }
                    # 'list_options': {
                        # 'type': 'dict',
                        # 'elements': 'list',
                    # },
                # }
            # ),
        },
        condition = {
            'type': 'dict',
            'options': {
                'matching': {
                    "type": 'str',
                    'choices': ['and', 'or'],
                    'default': 'and'
                },
                'type': {
                    "required": True,
                    "type": 'str',
                },
                'options': {
                    'type': 'dict'
                }
            },
        },
    )
    module_options = {
        'required_if': [
            ('command', 'create', ('sections', 'skip_if_existed'), False),
            ('command', 'delete', ('sections',), False),
            ('command', 'update', ('sections',), False),
            ('command', 'find_sections', ('condition',), False),
            ('command', 'commit', ("config",), True),
            ('command', 'revert', ("config",), True),
            ('command', 'reset', (), False),
        ],
    }

    # seed the result dict in the object
    # we primarily care about changed and state
    # changed is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = {
        "changed": False,
        "failed": False,
        'msg': "",
        'uci': {},
    }

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        **module_options
    )

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    # if module.check_mode:
        # module.exit_json(**result)

    uci = UciHandler(module)

    # use whatever logic you need to determine whether or not this module
    # made any modifications to your target
    try:
        msg = 'ok'
        changed = False
        if module.params['command'] == 'show':
            uci_dict = uci.show(config=module.params['config'])
        elif module.params['command'] == 'find_sections':
            uci_dict = uci.find_sections(module.params['config'],
                    section_type=module.params['condition']['type'],
                    opt_cond=module.params['condition']['matching'],
                    options=module.params['condition']['options']
            )
        elif module.params['command'] == 'create':
            for section in module.params['sections']:
                section_name = ""
                if "name" in section.keys():
                    section_name = section['name']
                uci.create_section(module.params['config'], section['type'],
                        skip_if_existed=module.params['skip_if_existed'],
                        section_name=section_name, options=section['options']
                )
            uci_dict = uci._show_changes()
            changed = True if uci_dict['create_or_update'] or uci_dict['delete'] else False
        elif module.params['command'] == 'delete':
            for section in module.params['sections']:
                if 'options' not in section.keys():
                    section['options'] = []
                if 'list_options' not in section.keys():
                    section['list_options'] = {}
                uci.delete(module.params['config'], section['name'], options=section['options'],
                           list_options=section['list_options']
                )
            uci_dict = uci._show_changes()
            changed = True if uci_dict['create_or_update'] or uci_dict['delete'] else False
        elif module.params['command'] == 'update':
            for section in module.params['sections']:
                uci.update(module.params['config'], section['name'], options=section['options'])
            uci_dict = uci._show_changes()
            changed = True if uci_dict['create_or_update'] or uci_dict['delete'] else False
        elif module.params['command'] == 'commit':
            if module.check_mode:
                uci_dict = uci._show_changes()
            else:
                uci_dict = uci.commit(module.params['config'])
                changed = True if uci_dict['create_or_update'] or uci_dict['delete'] else False
        elif module.params['command'] == 'revert':
            uci_dict = uci.revert(module.params['config'])
            changed = True if uci_dict['create_or_update'] or uci_dict['delete'] else False
        elif module.params['command'] == 'reset':
            uci_dict = uci._show_changes()
            configs = []
            for _, conf_data in uci_dict.items():
                for conf in conf_data.keys():
                    if conf not in configs:
                        configs.append(conf)
            for conf in configs:
                uci.revert(conf)
            changed = True if uci_dict['create_or_update'] or uci_dict['delete'] else False
        else:
            raise ValueError(f"Unsupported module params <{module.params}>")
        failed = False
    except:
        msg = traceback.format_exc()
        uci_dict = {}
        _uci_changes_dict = uci._show_changes()
        _uci_chagnes_configs = []
        for k, v in _uci_changes_dict.items():
            for conf in v.keys():
                if conf not in _uci_chagnes_configs:
                    _uci_chagnes_configs.append(conf)
        for conf in _uci_chagnes_configs:
            uci.revert(conf)
        failed = True
        changed = False
    result = uci.to_ansible(changed=changed, failed=failed, msg=msg, uci=uci_dict)

    # during the execution of the module, if there is an exception or a
    # conditional state that effectively causes a failure, run
    # AnsibleModule.fail_json() to pass in the message and the result
    if result['failed']:
        module.fail_json(**result)

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
