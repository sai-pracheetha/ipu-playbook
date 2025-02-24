#!/usr/bin/python
#
# Copyright 2022-2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Common Python APIs and utilities for Intel® Infrastructure Processing Unit (Intel® IPU)

import subprocess
import os
import time
import re
import yaml
import sys


def run_cmd(cmd, output=False, check_returncode=True):
    """
    Execute a command in a subprocess.
    :param cmd: The command to be executed as a string.
    :param output: If True, capture and return the command's stdout.
    :param check_returncode: If True, check the command's return code and raise an error if not 0.
    :return: The stdout of the command if output is True, otherwise None.
    """
    print(f'Executing: {cmd}')
    # Use a context manager to ensure the subprocess is cleaned up after execution
    with subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE if output else None, stderr=subprocess.PIPE, encoding="utf-8") as s:
        outs, errs = s.communicate() if output else (None, None)
        # Check the return code if required
        if check_returncode and s.returncode != 0:
            raise subprocess.CalledProcessError(s.returncode, cmd, output=outs, stderr=errs)
        return outs.strip() if output else None


def ping_test(dst_ip, count=4, vm=None):
    if vm:
        cmd = f"ip netns exec {vm} ping {dst_ip} -c {count}"
    else:
        cmd = f"ping {dst_ip} -c {count}"
    try:
        result = run_cmd(cmd, output=True)
        pkt_loss = 100
        if result:
            match = re.search(r'(\d*)% packet loss', result)
            if match:
                pkt_loss = int(match.group(1))
            if f"{count} received, 0% packet loss" in result:
                print(f"PASS: Ping successful to destination {dst_ip}\n")
                return True
            else:
                raise RuntimeError(f"FAIL: Ping Failed to destination {dst_ip} with" f" {pkt_loss}% loss\n")
    except Exception as E:
        print(f"Ping run failed with error:'{E}'\n")
        return False


def split_mac(mac_address):
    # Split the MAC address by colons
    octets = mac_address.split(":")

    # Join the first three octets and the last three octets
    first_octet = "".join(octets[:2])
    second_octet = "".join(octets[2:4])
    third_octet = "".join(octets[4:])

    print("first octet {} second octet {} third octet {}".format(first_octet, second_octet, third_octet))
    return first_octet, second_octet, third_octet


def split_mac_2(mac_address):
    # Split the MAC address by colons
    octets = mac_address.split(":")

    # Join the first three octets and the last three octets
    first_split = "".join(octets[:2])
    second_split = "".join(octets[2:])

    return first_split, second_split


def ip_dec_to_hex(ip_address):
    octets = ip_address.split('.')
    hex_octets = [f"{int(octet):02X}" for octet in octets]
    return "".join(hex_octets)


class TestSetup:
    def __init__(self, config_file=''):
        self.config_file = config_file
        self.test_config = {}

        with open(self.config_file, "r") as file:
            self.test_config = yaml.safe_load(file)

        if self.test_config is None:
            print("Unable to parse the config.yaml to generate test configuration")
            sys.exit()

    def ssh_command(self, server_name, command, output=True, check_returncode=True):
        """
        Execute a command on a remote server via SSH.
        :param server_name: The name of the server ('host', 'imc', or 'acc').
        :param command: The command to be executed on the remote server.
        :return: A dictionary with the return code and the command's output.
        """
        imc_ip = self.test_config['imc']['ssh']['ip']
        acc_ip = self.test_config['acc']['ssh']['ip']
        # SSH command templates
        imc_access = f'ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@{imc_ip}'
        acc_access = f'{imc_access} ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@{acc_ip}'

        # Determine the appropriate SSH command based on the server name
        if server_name == 'host':
            full_cmd = command
        elif server_name == 'imc':
            full_cmd = f'{imc_access} "{command}"'
        elif server_name == 'acc':
            full_cmd = f'{acc_access} "{command}"'
        else:
            raise ValueError(f"Unknown server name: {server_name}")

        # Execute the command and capture the output
        output = run_cmd(full_cmd, output=output, check_returncode=check_returncode)

        # Return the result as a dictionary
        return {'rc': 0, 'output': output}

    def reboot_imc(self):
        """
        Reboot the IMC, this will also reboot the ACC
        """
        imc_command_list = ["ipu-update -i",
                            "cat /etc/issue",
                            "ls -l /etc/hwconf | grep -i active",
                            "lspci -n | egrep '1452|1453'",
                            "ip -br a",
                            "modinfo idpf | grep version",
                            "ethtool -i enp0s1f0 | grep -A 1 idpf"]

        acc_command_list = ["cat /etc/issue",
                            "ip -br a",
                            "modinfo idpf | grep version",
                            "ethtool -i enp0s1f0 | grep -A 1 idpf"]

        print("\n----------------IMC Pre-Reboot Checks----------------")
        try:
            for command in imc_command_list:
                result = self.ssh_command('imc', command)
                print(f"output:\n{result['output']}\n")
        except Exception as e:
            print(f"ERROR: IMC Pre-reboot Checks failed,Exception \n{e}")
            return False
        time.sleep(2)

        print("\n----------------ACC Pre-Reboot Checks----------------")
        try:
            for command in acc_command_list:
                result = self.ssh_command('acc', command)
                print(f"output:\n{result['output']}\n")
        except Exception as e:
            print(f"ERROR: IMC Pre-reboot Checks failed,Exception \n{e}")
            return False
        time.sleep(2)

        print("\n----------------Rebooting IMC, Please wait for IMC and ACC to bootup----------------")
        command = "reboot"
        result = self.ssh_command('imc', command)
        print(f"output:\n{result['output']}\n")

        time.sleep(20)
        max_retries = 15  # Adjust based on your server's reboot time
        for retry in range(max_retries):
            display_string = "-" * 5 * retry
            print(f"Rebooting {display_string}")
            time.sleep(20)  # Adjust based on your server's reboot time
        print(f"Rebooting {display_string} COMPLETED")

        print("\n----------------IMC Post-Reboot Checks----------------")
        try:
            for command in imc_command_list:
                result = self.ssh_command('imc', command)
                print(f"output:\n{result['output']}\n")
        except Exception as e:
            print(f"ERROR: IMC Post-reboot Checks failed,Exception \n{e}")
            return False
        time.sleep(2)

        print("\n----------------ACC Post-Reboot Checks----------------")
        try:
            for command in acc_command_list:
                result = self.ssh_command('acc', command)
                print(f"output:\n{result['output']}\n")
        except Exception as e:
            print(f"ERROR: IMC Post-reboot Checks failed,Exception \n{e}")
            return False
        time.sleep(2)

        return True

    def copy_scripts(self):
        """
        Copies configuration scripts from the host to the IMC and then to the ACC.

        :param host_path: Path to the configuration scripts on the host machine
        :param imc_path: Destination path on the IMC
        :param acc_path: Destination path on the ACC
        """
        host_path = self.test_config['test_params']['host_path']
        imc_path = self.test_config['test_params']['imc_path']
        acc_path = self.test_config['test_params']['acc_path']
        imc_ip = self.test_config['imc']['ssh']['ip']
        acc_ip = self.test_config['acc']['ssh']['ip']

        command = f'mkdir -p {imc_path}'
        try:
            result = self.ssh_command('imc', command)
            print(f"output:\n{result['output']}\n")
        except Exception as e:
            print(f"Failed with exception:\n{e}")

        command = f'mkdir -p {acc_path}'
        try:
            result = self.ssh_command('acc', command)
            print(f"output:\n{result['output']}\n")
        except Exception as e:
            print(f"Failed with exception:\n{e}")

        # Copy the configuration scripts from host to IMC
        command = f'scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -r {host_path}  root@{imc_ip}:{imc_path}/'
        try:
            result = self.ssh_command('host', command)
            print(f"output:\n{result['output']}\n")
        except Exception as e:
            print(f"Failed with exception:\n{e}")

        command = f'chmod +x {imc_path}/{host_path}/*'
        try:
            result = self.ssh_command('imc', command)
            print(f"output:\n{result['output']}\n")
        except Exception as e:
            print(f"Failed with exception:\n{e}")

        # Copy the configuration scripts from IMC to ACC
        command = f'scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -r {imc_path}/{host_path} root@{acc_ip}:{acc_path}/'
        try:
            result = self.ssh_command('imc', command)
            print(f"output:\n{result['output']}\n")
        except Exception as e:
            print(f"Failed with exception:\n{e}")

        command = f'chmod +x {acc_path}/{host_path}/*'
        try:
            result = self.ssh_command('acc', command)
            print(f"output:\n{result['output']}\n")
        except Exception as e:
            print(f"Failed with exception:\n{e}")

    def get_interface_info(self, server_name, interface_name):
        """
        Retrieve information about a network interface on a remote server.

        :param server_name: The name of the server where the interface is located.
        :param interface_name: The name of the network interface to query.
        :return: A dictionary containing various pieces of information about the interface.
        """
        # Initialize an empty dictionary to store interface information
        interface_info = {}

        # Define a mapping of server names to host IDs
        host_id = {
            'host': '0x0',
            'acc': '0x4',
            'imc': '0x5'
        }

        # Command to get basic interface information using ifconfig
        cmd = f"ifconfig {interface_name}"
        try:
            result = self.ssh_command(server_name, cmd)
        except Exception as e:
            print(f"Failed to run ifconfig on '{interface_name}': {e}")
            return interface_info

        output = result['output']

        # Regex patterns to extract IP, MAC, and other fields
        ip_pattern = re.compile(r'inet (\d+\.\d+\.\d+\.\d+)')
        mac_pattern = re.compile(r'ether ([0-9a-fA-F:]{17})')
        mtu_pattern = re.compile(r'mtu (\d+)')

        # Search for patterns in the output and populate the dictionary
        interface_info['ip'] = ip_pattern.search(output).group(1) if ip_pattern.search(output) else None
        interface_info['mac'] = mac_pattern.search(output).group(1) if mac_pattern.search(output) else None
        interface_info['mtu'] = mtu_pattern.search(output).group(1) if mtu_pattern.search(output) else None

        # Command to get detailed interface information using ethtool
        cmd = f"ethtool -i {interface_name}"
        try:
            result = self.ssh_command(server_name, cmd)
        except Exception as e:
            print(f"Failed to run ethtool on '{interface_name}': {e}")
            return interface_info

        output = result['output']

        # Parse ethtool output and add to the dictionary
        for line in output.split('\n'):
            field = line.split(': ')
            if len(field) == 2:
                interface_info[field[0].strip()] = field[1].strip()

        # Check if the driver is not 'idpf' and return the info collected so far
        if interface_info.get('driver') != 'idpf':
            return interface_info

        # Command to get additional interface information for 'idpf' interface from IMC
        cmd = f"cli_client -q -c | grep 'host_id: {host_id[server_name]}' | grep '{interface_info['mac']}'"
        try:
            result = self.ssh_command('imc', cmd)
        except Exception as e:
            print(f"Failed to run cli_client on '{interface_name}': {e}")
            return interface_info

        output = result['output']

        # Regex pattern to extract additional fields for 'idpf' driver
        pattern = re.compile(r'fn_id:\s+(\w+)\s+host_id:\s+(\w+)\s+is_vf:\s+(\w+)\s+vsi_id:\s+(\w+)\s+vport_id\s+(\w+)\s+is_created:\s+(\w+)\s+is_enabled:\s+(\w+)\s+mac\s+addr:\s+([0-9a-fA-F:]{17})')
        match = pattern.search(output)

        # Populate the dictionary with additional information if available
        if match:
            interface_info.update({
                'fn_id': match.group(1),
                'host_id': match.group(2),
                'is_vf': match.group(3),
                'vsi_id': match.group(4),
                'vport_id': match.group(5),
                'is_created': match.group(6),
                'is_enabled': match.group(7),
                'mac_addr': match.group(8)
            })

            # Calculate additional fields based on 'vsi_id'
            if interface_info['vsi_id']:
                interface_info['vsi_num'] = str(int(interface_info['vsi_id'], 16))
                port_offset = str(int(interface_info['vsi_id'], 16) + 16)
                interface_info['port'] = port_offset

        return interface_info

    def load_custom_package(self, p4):

        if '.p4' in p4:
            p4 = p4.rstrip('.p4')

        imc_path = self.test_config['test_params']['imc_path']
        acc_path = self.test_config['test_params']['acc_path']
        imc_ip = self.test_config['imc']['ssh']['ip']
        acc_ip = self.test_config['acc']['ssh']['ip']
        p4_artifacts = self.test_config['test_params']['p4_artifacts']
        pf_mac = self.test_config['test_params']['pf_mac']
        vf_mac = self.test_config['test_params']['vf_mac']
        cxp_num_pages = self.test_config['test_params']['cxp_num_pages']
        comm_vports = self.test_config['test_params']['comm_vports']
        p4_pkg = f'{p4}.pkg'
        host_p4_pkg_path = f'{p4_artifacts}/{p4_pkg}'
        p4_script_file = f'{p4}/load_custom_pkg.sh'
        p4_package_file = f'{p4}/{p4_pkg}'

        # Copy P4 artifacts fxp-net_linux-networking and create load_custom_pkg.sh to update the p4 package
        if p4 == 'fxp-net_linux-networking':

            if not os.path.isfile(host_p4_pkg_path):
                print(f"ERROR: {p4_pkg} is not present in location {host_p4_pkg_path}")
                print("ERROR: Check test_params[p4_artifacts] field in config.yaml")
                return False

            print("\n----------------Copy P4 artifacts and create load_custom_pkg.sh in localhost repo----------------")
            # Create the load_custom_pkg.sh script in localhost
            if cxp_num_pages == '' and comm_vports == '':
                ipsec_config = ''
            else:
                ipsec_config = '''sed -i 's/cxp_num_pages = .*;/cxp_num_pages = '''+cxp_num_pages+''';/g' \\$CP_INIT_CFG
    sed -i 's/comm_vports = .*/comm_vports = '''+comm_vports+''';/g' \\$CP_INIT_CFG'''

            cmd = 'cat <<EOF > ./'+p4_script_file+'''
#!/bin/sh
CP_INIT_CFG=/etc/dpcp/cfg/cp_init.cfg
echo "Checking for custom package..."
sed -i 's/pf_mac_address = "00:00:00:00:03:14";/pf_mac_address = "'''+pf_mac+'''";/g' \\$CP_INIT_CFG
sed -i 's/vf_mac_address = "";/vf_mac_address = "'''+vf_mac+'''";/g' \\$CP_INIT_CFG
if [ -e /work/scripts/fxp-net_linux-networking.pkg ]; then
    echo "Custom package fxp-net_linux-networking.pkg found. Overriding default package"
    cp  /work/scripts/fxp-net_linux-networking.pkg /etc/dpcp/package/
    rm -rf /etc/dpcp/package/default_pkg.pkg
    ln -s /etc/dpcp/package/fxp-net_linux-networking.pkg /etc/dpcp/package/default_pkg.pkg
    sed -i 's/sem_num_pages = .*;/sem_num_pages = 28;/g' \\$CP_INIT_CFG
    sed -i 's/lem_num_pages = .*;/lem_num_pages = 32;/g' \\$CP_INIT_CFG
    sed -i 's/mod_num_pages = .*;/mod_num_pages = 2;/g' \\$CP_INIT_CFG
    sed -i 's/acc_apf = 4;/acc_apf = 16;/g' \\$CP_INIT_CFG
    '''+ipsec_config+'''
else
    echo "No custom package found. Continuing with default package"
fi
EOF
'''
            host_command_list = [f"rm -rf ./{p4}",
                                 f"cp -rf {p4_artifacts} {p4}",
                                 cmd,
                                 f"chmod +x ./{p4_script_file}",
                                 f"ls -lrt {p4}",
                                 f"cat ./{p4_script_file}",
                                 f"md5sum {p4_package_file}"]

            for command in host_command_list:
                try:
                    result = self.ssh_command('host', command)
                    print(f"output:\n{result['output']}\n")
                except Exception as e:
                    print(f"Failed with exception:\n{e}")
            time.sleep(2)

            # Send file:load_custom_pkg.sh from local host to IMC and ACC using SCP
            if os.path.isfile(p4_script_file) and os.path.isfile(p4_package_file):
                print("\n----------------Copy P4 artifacts and load_custom_pkg.sh script from Host to IMC----------------")
                print(f"\nCleanup the artifacts and script in {imc_path}/{p4} on the IMC")
                imc_command_list = [f"rm -rf {imc_path}/{p4}",
                                    f"mkdir -p {imc_path}",
                                    f"rm -f /work/scripts/{p4_pkg}",
                                    "ls -lrt /work/scripts/"]
                try:
                    for command in imc_command_list:
                        result = self.ssh_command('imc', command)
                        print(f"output:\n{result['output']}\n")
                except Exception as e:
                    print(f"Cleanup of P4 artifacts failed in IMC with exception:\n{e}")

                # Copy the artifacts and script from host to IMC
                print(f"\nCopy the artifacts and script in {p4} to {imc_path}/{p4} on the IMC")
                command = f'scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -r {p4} root@{imc_ip}:{imc_path}/'
                try:
                    result = self.ssh_command('host', command)
                    print(f"output:\n{result['output']}\n")
                except Exception as e:
                    print(f"Failed with exception:\n{e}")

                print(f"Copy the script {imc_path}/{p4_script_file} to /work/scripts/load_custom_pkg.sh on the IMC")
                print(f"Copy the P4 Package {imc_path}/{p4_package_file} to /work/scripts/ folder on the IMC")
                imc_command_list = [f"ls -lrt {imc_path}/{p4}",
                                    f"cp -f {imc_path}/{p4_script_file} /work/scripts/",
                                    f"cp -f {imc_path}/{p4_package_file} /work/scripts/",
                                    "chmod +x /work/scripts/load_custom_pkg.sh",
                                    "ls -lrt /work/scripts/",
                                    "cat /work/scripts/load_custom_pkg.sh",
                                    f"md5sum /work/scripts/{p4_pkg}"]
                try:
                    for command in imc_command_list:
                        result = self.ssh_command('imc', command)
                        print(f"output:\n{result['output']}\n")
                except Exception as e:
                    print(f"Failed with exception:\n{e}")
                time.sleep(2)

                # Copy the P4 artifacts from IMC to ACC
                print("\n----------------Copy P4 artifacts from IMC to ACC----------------")
                print(f"\nCopy the artifacts and script in {p4} to {acc_path}/{p4} on the ACC")
                command = 'ls -lrt /opt/p4/p4sde/bin/'
                try:
                    result = self.ssh_command('acc', command)
                    print(f"output:\n{result['output']}\n")
                except Exception as e:
                    print(f"P4 SDE binaries are missing, extracting ACC tarball /opt/p4.tar.gz:\nException {e}")
                    command = 'tar -xvf /opt/p4.tar.gz -C /opt/ > /dev/null 2>&1 &'
                    result = self.ssh_command('acc', command)
                    time.sleep(30)
                    command = 'ls /opt/p4/p4sde/bin/'
                    result = self.ssh_command('acc', command)
                    print(f"output:\n{result['output']}\n")

                acc_command_list = [f"rm -rf {acc_path}/{p4}",
                                    f"mkdir -p {acc_path}"]
                try:
                    for command in acc_command_list:
                        result = self.ssh_command('acc', command)
                        print(f"output:\n{result['output']}\n")
                except Exception as e:
                    print(f"Cleanup of P4 artifacts failed in ACC with exception:\n{e}")

                command = f'scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -r {imc_path}/{p4} root@{acc_ip}:{acc_path}/'
                try:
                    result = self.ssh_command('imc', command)
                except Exception as e:
                    print(f"Failed with exception:\n{e}")

                acc_command_list = [f"ls -lrt {acc_path}/{p4}",
                                    f"md5sum {acc_path}/{p4_package_file}"]
                try:
                    for command in acc_command_list:
                        result = self.ssh_command('acc', command)
                        print(f"output:\n{result['output']}\n")
                except Exception as e:
                    print(f"P4 artifacts copy failed in ACC with exception:\n{e}")
                time.sleep(2)
            else:
                print(f"ERROR: Script {p4_script_file} and {p4_package_file} is missing in Repo")

        elif p4 == 'default':
            print("\n----------------Create load_custom_pkg.sh for default_pkg.pkg in localhost repo----------------")
            p4_script_file = f'{p4}/load_custom_pkg.sh'
            cmd = 'cat <<EOF > ./'+p4_script_file+'''
#!/bin/sh
CP_INIT_CFG=/etc/dpcp/cfg/cp_init.cfg
echo "Checking for custom package..."
if [ -e p4_custom.pkg ]; then
    echo "Custom package p4_custom.pkg found. Overriding default package"
    cp  p4_custom.pkg /etc/dpcp/package/
    rm -rf /etc/dpcp/package/default_pkg.pkg
    ln -s /etc/dpcp/package/p4_custom.pkg /etc/dpcp/package/default_pkg.pkg
    sed -i 's/sem_num_pages = 1;/sem_num_pages = 25;/g' \\$CP_INIT_CFG
else
    echo "No custom package found. Continuing with default package"
fi
'''
            host_command_list = [f'mkdir {p4}',
                                 cmd,
                                 f"chmod +x ./{p4_script_file}",
                                 f"ls -lrt {p4_script_file}",
                                 f"cat {p4_script_file}"]

            for command in host_command_list:
                try:
                    result = self.ssh_command('host', command)
                    print(f"output:\n{result['output']}\n")
                except Exception as e:
                    print(f"Failed with exception:\n{e}")
            time.sleep(2)

            # Copy file:load_custom_pkg.sh from local host to IMC /work/scripts/load_custom_pkg.sh
            if os.path.isfile(p4_script_file):
                print("\n----------------Copy load_custom_pkg.sh from the Host to IMC----------------")
                print(f"\nCopy the script {p4_script_file} to /work/scripts/load_custom_pkg.sh on the IMC")
                # Copy the artifacts and script from host to IMC
                command = f'scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -r {p4_script_file} root@{imc_ip}:/work/scripts/load_custom_pkg.sh'
                try:
                    result = self.ssh_command('host', command)
                    print(f"output:\n{result['output']}\n")
                except Exception as e:
                    print(f"Failed with exception:\n{e}")

                imc_command_list = ["chmod +x /work/scripts/load_custom_pkg.sh",
                                    "ls -lrt /work/scripts/",
                                    "cat /work/scripts/load_custom_pkg.sh"]
                try:
                    for command in imc_command_list:
                        result = self.ssh_command('imc', command)
                        print(f"output:\n{result['output']}\n")
                except Exception as e:
                    print(f"Failed with exception:\n{e}")
                time.sleep(2)

        command = "ls -lrt /etc/dpcp/package/default_pkg.pkg"
        result = self.ssh_command('imc', command)
        print(f"output:\n{result['output']}\n")
        out = result['output'].rstrip('\n')
        out = out.split(' ')

        print(f"Package: {out[len(out)-1]} is loaded on the IMC")

        # reboot IMC for custom package to be loaded
        print(f"Reboot IMC for package:{p4} to be updated")
        self.reboot_imc()

        # recheck after IMC boot that the P4 package is updated
        command = "ls -lrt /etc/dpcp/package/default_pkg.pkg"
        result = self.ssh_command('imc', command)
        print(f"output:\n{result['output']}\n")
        out = result['output'].rstrip('\n')
        out = out.split(' ')

        if p4 not in out[len(out)-1]:
            print(f"ERROR: P4 Package:{p4} failed to load on the IMC after reboot")
            return False

        print(f"\n PASS: P4 Package: {out[len(out)-1]} is loaded on the IMC after reboot")
        return True


class tmux_term:
    def __init__(self, test_setup, tmux_name="", tmux_override=False):
        # Initialize a new tmux terminal session
        if not tmux_name:
            raise ValueError("Error: No tmux name specified!")
        self.tmux_name = tmux_name
        self.test_setup = test_setup
        # Check if the specified tmux session already exists
        command = 'tmux ls'
        try:
            result = self.test_setup.ssh_command('host', command, check_returncode=False)
        except Exception as e:
            raise Exception(f"Failed to list tmux sessions with exception:\n{e}")

        # Parse the output to find an existing session
        lines = result['output']
        found = any(self.tmux_name in line for line in lines.split('\n'))

        # If the session is found and override is allowed, kill the existing session
        if found and tmux_override:
            command = f'tmux kill-session -t {self.tmux_name}'
            self.test_setup.ssh_command('host', command)

        # If the session was not found or was killed, create a new one
        if not found or tmux_override:
            command = f'tmux new-session -d -s {self.tmux_name}'
            self.test_setup.ssh_command('host', command)

    def tmux_send_keys(self, cmd, delay=1, output=True):
        # Send a command to the tmux session and optionally capture the output
        time.sleep(0.5)  # Short delay before sending the command

        if output:
            # Set up piping to capture the output of the command
            output_file = os.path.join(os.getcwd(), 'tmux_output.txt')
            command = f'tmux pipe-pane -t {self.tmux_name} "cat > {output_file}"'
            self.test_setup.ssh_command('host', command)

        # Send the actual command to the tmux session
        command = f'tmux send-keys -t {self.tmux_name} "{cmd}" C-m'
        self.test_setup.ssh_command('host', command)

        if output:
            # Wait for the specified delay to allow the command to execute and output to be captured
            if delay > 0:
                time.sleep(delay)

            # Stop piping the output
            command = f'tmux pipe-pane -t {self.tmux_name}'
            self.test_setup.ssh_command('host', command)

            # Read the captured output from the file
            with open(output_file, "r") as f:
                result = f.read()

        return result
