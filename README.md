Home Network Ansible Scripts
========================================

how to use
----------------------------------------
1. install the ansible requirements.
```
ansible-galaxy install -r requirements.yml
```

2. install the python requirements, via `pip` or `apt`
```
pip install tomlkit ansible-mitogen
apt install python3-tomlkit ansible-mitogen
```

3. find `mitogen` path and then modify the `./ansible.cfg`
```
python3 -c "import os, ansible_mitogen; print(os.path.join(os.path.dirname(ansible_mitogen.__file__), 'plugins', 'strategy'))"
```

4. Prepare your ansible user on your VPS machines
```
# adduser <user>      # add your login user
# passwd <user>       # change your user's password
# usermod -a -G sudo <user> # add your login user into group sudo
# apt install python3       # install the ansible guest dependencies
```

5. Make your own `all.yml` from `all-example.yml` template
```
cp inventory/group_vars/all-example.yml inventory/group_vars/all.yml
$EDITOR inventory/group_vars/all.yml
```

6. Update your hosts info in `inventory/*.yml` to adapt your network structure

7. Execute the playbook script.
```
ansible-playbook -i inventory/ playbook.yml                 # execute all tasks
ansible-playbook -i inventory/ playbook.yml --tags <xxx>    # execute only the tasks under tag xxx
```

LAN Structure
----------------------------------------
```
                 +------------+
      +----------|  Laptop A  |--------+
      |          +------------+        |
 (wireguard            |          (wireguard
 when IPv6)       (wg in Xray)     when IPv6)
      |                |               |
      |          +-----------+         |
      |          |   VPS A   |         |
      |          +-----------+         |
      |           /         \          |
      |      (WireGuard in Xray)       |
      |        /       ^       \       |
+------------+         |         +------------+
|  Router A  | <- (wg direct) -> |  Router B  |
+------------+         |         +------------+
      |        \       v       /       |
      |      (WireGuard in Xray)       |
      |           \         /          |
+------------+   +-----------+   +------------+
|   LAN  A   |   |   VPS B   |   |   LAN  B   |
+------------+   +-----------+   +------------+
```

As the above diagram, `Router A` and `Router B` (with their `LAN A` & `LAN B`) are combined to a LAN by `wireguard` VPN protocol, similar as the `VPS A` and `VPS B`.
Routers and VPS are combined to a LAN via `wireguard` as well, but the `wireguard` UDP data are wrapped in `Xray` proxy protocol.
For the `Laptop A` outside of the giant LAN, use `IPv6` tunnel with `wireguard` protocol to connect to the routers directly if possible;
othterwise, use `VPS A` or `VPS B` to forward the LAN data, with `Xray` wrapping as well.
