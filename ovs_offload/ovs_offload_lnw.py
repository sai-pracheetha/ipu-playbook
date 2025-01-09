#!/usr/bin/python
#
# Copyright 2022-2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Python tool to setup Linux Networking with OVS Offload on Intel® Infrastructure Processing Unit (Intel® IPU)

import sys,argparse
import os

# Add the parent directory to the system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.utils import *

def build_p4rt_config(test_setup = None):

    if test_setup == None:
        print("Unable to parse the config.yaml to generate test configuration")
        sys.exit()

    host_idpf_intf= test_setup.test_config['test_params']['idpf_interface']
    vf_list = test_setup.test_config['test_params']['vf_interfaces']
    acc_pr_list = test_setup.test_config['test_params']['acc_pr_interfaces']
    vm_ip_list = test_setup.test_config['test_params']['ip_list']
    path = test_setup.test_config['test_params']['host_path']

    print("---------- Generating Configs to run infrap4d, p4rt and OVS ----------")

    if len(vf_list) != len(acc_pr_list):
        print("ERROR: number of vfs and ACC PRs should be the same")
        return None

    host_command_list = []
    cmd = f"mkdir -p {path}"
    host_command_list.append(cmd)

    file = f'{path}/1_host_idpf.sh'
    host_idpf = 'cat <<EOF > ./'+file+'''
#!/bin/sh
#Load the driver
echo "Load the IDPF Driver on the Host"
modprobe idpf
sleep 4

echo ""
echo "Check the Interfaces are up"
ip -br a
#Setup number of sriov devices on the IDPF interface
echo "Create SRIOV VFs on IDPF interface '''+host_idpf_intf+'''"
echo 8 > /sys/class/net/'''+host_idpf_intf+'''/device/sriov_numvfs

echo ""
echo "Wait for the interfaces to come up"
sleep 5
ip -br a
EOF
'''
    host_command_list.append(host_idpf)
    host_command_list.append(f"chmod +x ./{file}")
    #host_command_list.append(f"./{file}")

    for command in host_command_list:
        try:
            result = test_setup.ssh_command('host', command)
        except Exception as e:
            print(f"Failed with exception:\n{e}")
    time.sleep(5)

    mac_list = []
    vf_to_acc = ''
    phy_to_acc = ''
    vf_to_vm = ''
    ovs_vxlan = ''
    local_vtep = test_setup.test_config['test_params']['local_vtep']
    remote_vtep = test_setup.test_config['test_params']['remote_vtep']
    local_br_tun = test_setup.test_config['test_params']['local_br_tun_ip']
    remote_br_tun = test_setup.test_config['test_params']['remote_br_tun_ip']
    vm_id = 0
    command_list = []
    cmd = f"mkdir -p {path}"
    command_list.append(cmd)
    for i in range(len(vf_list)):

        if str(vf_list[i]) == '0' or str(vf_list[i]) == '1':
        #Physical port   VSI_ID  PORT             ACC port representer  VSI_ID    PORT
        #Phy port 0      (0x0)    0     <---->    enp0s1f0d10         (0x11) 17   33
            acc_pr = test_setup.get_interface_info(server_name='acc', interface_name=acc_pr_list[i])
            phy_to_acc += f"""echo ""
echo "IPU Physical Port {vf_list[i]} maps to "
echo "ACC IDPF Interface {acc_pr_list[i]} MAC ({acc_pr['mac']})  VSI ({acc_pr['vsi_id']}:{acc_pr['vsi_num']})  PORT ({acc_pr['port']})"
p4rt-ctl add-entry br0 linux_networking_control.rx_source_port "vmeta.common.port_id={vf_list[i]},zero_padding=0,action=linux_networking_control.set_source_port({vf_list[i]})"
p4rt-ctl add-entry br0 linux_networking_control.rx_phy_port_to_pr_map "vmeta.common.port_id={vf_list[i]},zero_padding=0,action=linux_networking_control.fwd_to_vsi({acc_pr['port']})"
p4rt-ctl add-entry br0 linux_networking_control.source_port_to_pr_map "user_meta.cmeta.source_port={vf_list[i]},zero_padding=0,action=linux_networking_control.fwd_to_vsi({acc_pr['port']})"
p4rt-ctl add-entry br0 linux_networking_control.tx_acc_vsi "vmeta.common.vsi={acc_pr['vsi_num']},zero_padding=0,action=linux_networking_control.l2_fwd_and_bypass_bridge({vf_list[i]})"
sleep 2

"""

            ovs_vxlan += f"""echo ""
echo "IPU Port {vf_list[i]} mapped to ACC Port {acc_pr_list[i]} MAC ({acc_pr['mac']})  VSI ({acc_pr['vsi_id']}:{acc_pr['vsi_num']}:{acc_pr['port']})"
echo "ACC Port {acc_pr_list[i]} is added to OVS bridge br-tun-{vf_list[i]}"
ovs-vsctl del-br br-tun-{vf_list[i]}
ovs-vsctl add-br br-tun-{vf_list[i]}
ovs-vsctl add-port br-tun-{vf_list[i]} {acc_pr_list[i]}

"""
        else:
            vf = test_setup.get_interface_info(server_name='host', interface_name=vf_list[i])
            acc_pr = test_setup.get_interface_info(server_name='acc', interface_name=acc_pr_list[i])
            vf_to_acc += f"""echo ""
echo "Host IDPF Interface {vf_list[i]} MAC ({vf['mac']})  VSI ({vf['vsi_id']}:{vf['vsi_num']})  PORT ({vf['port']}) maps to"
echo "ACC  IDPF Interface {acc_pr_list[i]} MAC ({acc_pr['mac']})  VSI ({acc_pr['vsi_id']}:{acc_pr['vsi_num']})  PORT ({acc_pr['port']})"
p4rt-ctl add-entry br0 linux_networking_control.tx_source_port "vmeta.common.vsi={vf['vsi_num']}/2047,priority=1,action=linux_networking_control.set_source_port({vf['port']})"
p4rt-ctl add-entry br0 linux_networking_control.source_port_to_pr_map "user_meta.cmeta.source_port={vf['port']},zero_padding=0,action=linux_networking_control.fwd_to_vsi({acc_pr['port']})"
p4rt-ctl add-entry br0 linux_networking_control.tx_acc_vsi "vmeta.common.vsi={acc_pr['vsi_num']},zero_padding=0,action=linux_networking_control.l2_fwd_and_bypass_bridge({vf['port']})"
p4rt-ctl add-entry br0 linux_networking_control.vsi_to_vsi_loopback "vmeta.common.vsi={acc_pr['vsi_num']},target_vsi={vf['vsi_num']},action=linux_networking_control.fwd_to_vsi({vf['port']})"
p4rt-ctl add-entry br0 linux_networking_control.vsi_to_vsi_loopback "vmeta.common.vsi={vf['vsi_num']},target_vsi={acc_pr['vsi_num']},action=linux_networking_control.fwd_to_vsi({acc_pr['port']})"
sleep 2

"""
            ovs_vxlan += f"""echo ""
echo "Host IDPF Interface {vf_list[i]} MAC ({vf['mac']})  VSI ({vf['vsi_id']}:{vf['vsi_num']}:{vf['port']}) maps to"
echo "ACC Port {acc_pr_list[i]} MAC ({acc_pr['mac']})  VSI ({acc_pr['vsi_id']}:{acc_pr['vsi_num']}:{acc_pr['port']})"
echo "ACC Port {acc_pr_list[i]} is added to OVS bridge br{vm_id}"
ip link del TEP{vm_id}
ovs-vsctl del-br br{vm_id}
ip link add dev TEP{vm_id} type dummy
ifconfig TEP{vm_id} {local_vtep[vm_id]}/24 up
ovs-vsctl add-br br{vm_id}
ovs-vsctl add-port br{vm_id} {acc_pr_list[i]}
ovs-vsctl add-port br{vm_id} vxlan{vm_id} -- set interface vxlan{vm_id} type=vxlan options:local_ip={local_vtep[vm_id]} options:remote_ip={remote_vtep[vm_id]} options:key=1{vm_id} options:dst_port=4789

"""
            vf_to_vm += f'''
echo ""
echo "Setup VM{vm_id} using ip netns (Network Namespace) to simulate a Virtual Machine"
echo "Add HOST VF {vf_list[i]} to the VM{vm_id} namespace"
ip netns del VM{vm_id}
ip netns add VM{vm_id}
sleep 1
ip link set {vf_list[i]} netns VM{vm_id}
ip netns exec VM{vm_id} ip addr add {vm_ip_list[vm_id]}/24 dev {vf_list[i]}
ip netns exec VM{vm_id} ifconfig {vf_list[i]} up
sleep 2
ip netns exec VM{vm_id} ip -br a

'''
            vm_id += 1

        mac_list.append(str(acc_pr['mac']))


    misc = """p4rt-ctl add-entry br0 linux_networking_control.ipv4_lpm_root_lut "user_meta.cmeta.bit16_zeros=4/65535,priority=2048,action=linux_networking_control.ipv4_lpm_root_lut_action(0)"
p4rt-ctl add-entry br0 linux_networking_control.tx_lag_table "user_meta.cmeta.lag_group_id=0/255,hash=0/7,priority=1,action=linux_networking_control.bypass"
p4rt-ctl add-entry br0 linux_networking_control.tx_lag_table "user_meta.cmeta.lag_group_id=0/255,hash=1/7,priority=1,action=linux_networking_control.bypass"
p4rt-ctl add-entry br0 linux_networking_control.tx_lag_table "user_meta.cmeta.lag_group_id=0/255,hash=2/7,priority=1,action=linux_networking_control.bypass"
p4rt-ctl add-entry br0 linux_networking_control.tx_lag_table "user_meta.cmeta.lag_group_id=0/255,hash=3/7,priority=1,action=linux_networking_control.bypass"
p4rt-ctl add-entry br0 linux_networking_control.tx_lag_table "user_meta.cmeta.lag_group_id=0/255,hash=4/7,priority=1,action=linux_networking_control.bypass"
p4rt-ctl add-entry br0 linux_networking_control.tx_lag_table "user_meta.cmeta.lag_group_id=0/255,hash=5/7,priority=1,action=linux_networking_control.bypass"
p4rt-ctl add-entry br0 linux_networking_control.tx_lag_table "user_meta.cmeta.lag_group_id=0/255,hash=6/7,priority=1,action=linux_networking_control.bypass"
p4rt-ctl add-entry br0 linux_networking_control.tx_lag_table "user_meta.cmeta.lag_group_id=0/255,hash=7/7,priority=1,action=linux_networking_control.bypass"
"""

    acc_path = test_setup.test_config['test_params']['acc_path']
    acc_p4_path = f'{acc_path}/fxp-net_linux-networking'
    file = f'{path}/es2k_skip_p4.conf'
    p4_config = 'cat <<EOF > ./'+file+'''
{
    "chip_list": [
        {
            "id": "asic-0",
            "chip_family": "mev",
            "instance": 0,
            "pcie_bdf": "0000:00:01.6",
            "iommu_grp_num": 7,
            "ctrl_map" : ["NETDEV","''' + '","'.join(mac_list) + '''" ,1]
        }
    ],
    "instance": 0,
    "cfgqs-idx": "0-15",
    "p4_devices": [
        {
            "device-id": 0,
            "eal-args": "--lcores=1-2 -a 00:01.6,vport=[0-1] -- -i --rxq=1 --txq=1 --hairpinq=1 --hairpin-mode=0x0",
            "p4_programs": [
                {
                    "program-name": "fxp-net_linux-networking",
                    "tdi-config": "'''+acc_p4_path+'''/tdi.json",
                    "p4_pipelines": [
                        {
                            "p4_pipeline_name": "main",
                            "context": "'''+acc_p4_path+'''/context.json",
                            "config": "'''+acc_p4_path+'''/ipu.bin",
                            "pipe_scope": [
                                0,
                                1,
                                2,
                                3
                            ],
                            "path": "'''+acc_p4_path+'''/"
                        }
                    ]
                }
            ],
            "agent0": "lib/libpltfm_mgr.so"
        }
    ]
}
EOF
'''
    command_list.append(p4_config)

    command_list.append(host_idpf)

    file = f'{path}/2_acc_infrap4d.sh'
    acc_infrap4d = 'cat <<EOF > ./'+file+'''
#!/bin/sh
#ACC Environment for Infrap4d:
echo ""
echo "Setup the environment in ACC to run Infrap4d"
export SDE_INSTALL=/opt/p4/p4sde
export P4CP_INSTALL=/opt/p4/p4-cp-nws
export DEPEND_INSTALL=\$P4CP_INSTALL
export no_proxy=localhost,127.0.0.1,192.168.0.0/16
export NO_PROXY=localhost,127.0.0.1,192.168.0.0/16
unset http_proxy
unset https_proxy

bash \$P4CP_INSTALL/sbin/setup_env.sh \$P4CP_INSTALL \$SDE_INSTALL \$DEPEND_INSTALL
sudo \$P4CP_INSTALL/sbin/copy_config_files.sh \$P4CP_INSTALL \$SDE_INSTALL

export OUTPUT_DIR='''+acc_p4_path+'''

echo ""
echo "Load the vfio-pci driver to bind the vfio-pci 00:01.6"
sudo modprobe vfio-pci
sudo /opt/p4/p4sde/bin/dpdk-devbind.py -b vfio-pci 00:01.6

echo ""
echo "Copy Infrap4d Config file es2k_skip_p4.conf to /usr/share/stratum/es2k/es2k_skip_p4.conf"
touch \$OUTPUT_DIR/ipu.bin
cp -f \$OUTPUT_DIR/es2k_skip_p4.conf /usr/share/stratum/es2k/es2k_skip_p4.conf

echo ""
echo "Verify the infrap4d config"
cat /usr/share/stratum/es2k/es2k_skip_p4.conf

#TLS CERTS
echo ""
echo "Generate the TLS Certs for Infrap4d"
cd /usr/share/stratum/
COMMON_NAME=localhost ./generate-certs.sh
sleep 2

echo ""
echo "Start Infrap4d"
#Start Infrap4d
/opt/p4/p4-cp-nws/sbin/infrap4d --nodetach
EOF
'''

    command_list.append(acc_infrap4d)

    file = f'{path}/3_acc_p4rt.sh'
    acc_p4rt = 'cat <<EOF > ./'+file+'''
#!/bin/sh

echo "Setup P4 Runtime Pipeline"
echo "P4 Artifacts are in Folder : OUTPUT_DIR='''+acc_p4_path+'''"
export SDE_INSTALL=/opt/p4/p4sde
export P4CP_INSTALL=/opt/p4/p4-cp-nws
export DEPEND_INSTALL=\$P4CP_INSTALL
export OUTPUT_DIR='''+acc_p4_path+'''
export PATH=/root/.local/bin:/root/bin:/usr/share/Modules/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/opt/p4/p4-cp-nws/bin:/opt/p4/p4-cp-nws/sbin

tdi_pipeline_builder --p4c_conf_file=/usr/share/stratum/es2k/es2k_skip_p4.conf --tdi_pipeline_config_binary_file=\$OUTPUT_DIR/fxp-net_linux-networking.pb.bin

sleep 2
echo ""
echo "Use p4rt-ctl set-pipe to setup the runtime pipeline"
p4rt-ctl set-pipe br0 \$OUTPUT_DIR/fxp-net_linux-networking.pb.bin \$OUTPUT_DIR/p4Info.txt
sleep 2
echo ""
echo "Get IDPF Interface MAC and VSI info from IMC command : cli_client -q -c"
echo "VSI (hexadecimal:decimal) PORT (VSI+16)"
echo "Use p4rt-ctl to configure the VFs -- ACC PR"
'''+vf_to_acc+'''
sleep 2
echo ""
echo "Use p4rt-ctl to configure the Physical Ports -- ACC PR"
'''+phy_to_acc+'''
sleep 2
echo ""
echo "Configure supporting p4 runtime tables for LPM and LAG bypass"
'''+misc+'''
EOF
'''
    command_list.append(acc_p4rt)

    file = f'{path}/acc_p4rt_delete.sh'
    acc_p4rt_delete = 'cat <<EOF > ./'+file+'''
#!/bin/sh

echo "Delete the P4 Runtime Rules"
export SDE_INSTALL=/opt/p4/p4sde
export P4CP_INSTALL=/opt/p4/p4-cp-nws
export DEPEND_INSTALL=\$P4CP_INSTALL
export OUTPUT_DIR='''+acc_p4_path+'''
export PATH=/root/.local/bin:/root/bin:/usr/share/Modules/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/opt/p4/p4-cp-nws/bin:/opt/p4/p4-cp-nws/sbin


echo "Use p4rt-ctl to remove the rules for the VFs -- ACC PR"
'''+vf_to_acc+'''
sleep 2
echo ""
echo "Use p4rt-ctl to remove the rules for Physical Ports -- ACC PR"
'''+phy_to_acc+'''
sleep 2
echo ""
echo "Remove supporting p4 runtime tables for LPM and LAG bypass"
'''+misc+'''
EOF
'''
    command_list.append(acc_p4rt_delete)

    delete_command = f'''
sed -i 's/add-entry/del-entry/g' {file}
sed -i 's/,action.*"/"/g' {file}
'''
    command_list.append(delete_command)

    file = f'{path}/4_acc_p4rt_dump.sh'
    acc_p4rt_dump = 'cat <<EOF > ./'+file+'''
#!/bin/sh

echo "Setup P4 Runtime Pipeline"
echo "P4 Artifacts are in Folder : OUTPUT_DIR='''+acc_p4_path+'''"
export SDE_INSTALL=/opt/p4/p4sde
export P4CP_INSTALL=/opt/p4/p4-cp-nws
export DEPEND_INSTALL=\$P4CP_INSTALL
export OUTPUT_DIR='''+acc_p4_path+'''
export PATH=/root/.local/bin:/root/bin:/usr/share/Modules/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/opt/p4/p4-cp-nws/bin:/opt/p4/p4-cp-nws/sbin


echo ""
echo "p4rt-ctl dump-entries br0 linux_networking_control.rx_source_port "
p4rt-ctl dump-entries br0 linux_networking_control.rx_source_port

#Run the p4rt-ctl dump-entries to display the table entries
echo ""
echo "Dump linux_networking_control.tx_source_port entries:"
echo "p4rt-ctl dump-entries br0 linux_networking_control.tx_source_port"
p4rt-ctl dump-entries br0 linux_networking_control.tx_source_port
sleep 1

echo ""
echo "Dump linux_networking_control.source_port_to_pr_map entries:"
echo "p4rt-ctl dump-entries br0 linux_networking_control.source_port_to_pr_map"
p4rt-ctl dump-entries br0 linux_networking_control.source_port_to_pr_map
sleep 1

echo ""
echo "Dump linux_networking_control.tx_acc_vsi entries:"
echo "p4rt-ctl dump-entries br0 linux_networking_control.tx_acc_vsi"
p4rt-ctl dump-entries br0 linux_networking_control.tx_acc_vsi
sleep 1

echo ""
echo "Dump linux_networking_control.vsi_to_vsi_loopback entries:"
echo "p4rt-ctl dump-entries br0 linux_networking_control.vsi_to_vsi_loopback"
p4rt-ctl dump-entries br0 linux_networking_control.vsi_to_vsi_loopback
sleep 1

echo ""
echo "Dump linux_networking_control.rx_phy_port_to_pr_map entries:"
echo "p4rt-ctl dump-entries br0 linux_networking_control.rx_phy_port_to_pr_map"
p4rt-ctl dump-entries br0 linux_networking_control.rx_phy_port_to_pr_map
sleep 1

echo ""
echo "Dump linux_networking_control.tx_lag_table entries:"
echo "p4rt-ctl dump-entries br0 linux_networking_control.tx_lag_table"
p4rt-ctl dump-entries br0 linux_networking_control.tx_lag_table
EOF
'''

    command_list.append(acc_p4rt_dump)
    file = f'{path}/5_acc_setup_ovs.sh'
    acc_setup_ovs = 'cat <<EOF > ./'+file+'''
#!/bin/sh

killall ovsdb-server
killall ovs-vswitchd

echo ""
echo "Setup the Environment to run OVS"
export SDE_INSTALL=/opt/p4/p4sde
export P4CP_INSTALL=/opt/p4/p4-cp-nws
export DEPEND_INSTALL=\$P4CP_INSTALL
export OUTPUT_DIR='''+acc_p4_path+'''
export PATH=/root/.local/bin:/root/bin:/usr/share/Modules/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/opt/p4/p4-cp-nws/bin:/opt/p4/p4-cp-nws/sbin
export RUN_OVS=/opt/p4/p4-cp-nws

rm -rf \$RUN_OVS/etc/openvswitch
rm -rf \$RUN_OVS/var/run/openvswitch
mkdir -p \$RUN_OVS/etc/openvswitch/
mkdir -p \$RUN_OVS/var/run/openvswitch

ovsdb-tool create \$RUN_OVS/etc/openvswitch/conf.db \$RUN_OVS/share/openvswitch/vswitch.ovsschema

echo ""
echo "Start the ovsdb-server"
ovsdb-server --remote=punix:\$RUN_OVS/var/run/openvswitch/db.sock --remote=db:Open_vSwitch,Open_vSwitch,manager_options --pidfile --detach

ovs-vsctl --no-wait init

echo ""
echo "Start the ovs-vswitchd"
mkdir -p /tmp/logs
ovs-vswitchd --pidfile --detach --mlockall --log-file=/tmp/logs/ovs-vswitchd.log

ovs-vsctl set Open_vSwitch . other_config:n-revalidator-threads=1
ovs-vsctl set Open_vSwitch . other_config:n-handler-threads=1
echo ""
echo "Verify OVS: ovsdb-server and ovs-vswitchd are running"
ovs-vsctl  show

ps -aux | grep ovs
EOF
'''
    command_list.append(acc_setup_ovs)
    file = f'{path}/6_acc_ovs_bridge.sh'
    acc_ovs_bridge = 'cat <<EOF > ./'+file+'''
#!/bin/sh

echo "Setup the Environment to run OVS"
export SDE_INSTALL=/opt/p4/p4sde
export P4CP_INSTALL=/opt/p4/p4-cp-nws
export DEPEND_INSTALL=\$P4CP_INSTALL
export OUTPUT_DIR='''+acc_p4_path+'''
export PATH=/root/.local/bin:/root/bin:/usr/share/Modules/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/opt/p4/p4-cp-nws/bin:/opt/p4/p4-cp-nws/sbin
export RUN_OVS=/opt/p4/p4-cp-nws

echo ""
echo "Setup an OVS Bridge br-int-1"

ovs-vsctl del-br br-int-1
ovs-vsctl del-br br-int-2
ovs-vsctl del-br br-tun-0
ovs-vsctl del-br br-tun-1

ip link del TEP0
ovs-vsctl del-br br0
ip link del TEP1
ovs-vsctl del-br br1
ip link del TEP2
ovs-vsctl del-br br2
ip link del TEP3
ovs-vsctl del-br br3
ip link del TEP4
ovs-vsctl del-br br4
ip link del TEP5
ovs-vsctl del-br br5
ip link del TEP6
ovs-vsctl del-br br6
ip link del TEP7
ovs-vsctl del-br br7
ip link del TEP8
ovs-vsctl del-br br8

ovs-vsctl add-br br-int-1
ovs-vsctl add-port br-int-1 enp0s1f0d4
ovs-vsctl add-port br-int-1 enp0s1f0d6
ovs-vsctl add-port br-int-1 enp0s1f0d7
ovs-vsctl add-port br-int-1 enp0s1f0d8
ovs-vsctl add-port br-int-1 enp0s1f0d9
ifconfig br-int-1 up

ovs-vsctl add-br br-int-2
ovs-vsctl add-port br-int-2 enp0s1f0d5
ovs-vsctl add-port br-int-2 enp0s1f0d10
ovs-vsctl add-port br-int-2 enp0s1f0d11
ovs-vsctl add-port br-int-2 enp0s1f0d12
ovs-vsctl add-port br-int-2 enp0s1f0d13
ifconfig br-int-2 up

sleep 2
ovs-vsctl show

echo "Check the interface configuration"
sleep 1
ip -br a

echo ""
echo "Configure the Host VM and Link Partner to test connectivity"
EOF
'''
    command_list.append(acc_ovs_bridge)


    file = f'{path}/acc_ovs_vxlan.sh'
    acc_ovs_vxlan = 'cat <<EOF > ./'+file+'''
#!/bin/sh

echo "Setup the Environment to run OVS"
export SDE_INSTALL=/opt/p4/p4sde
export P4CP_INSTALL=/opt/p4/p4-cp-nws
export DEPEND_INSTALL=\$P4CP_INSTALL
export OUTPUT_DIR='''+acc_p4_path+'''
export PATH=/root/.local/bin:/root/bin:/usr/share/Modules/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/opt/p4/p4-cp-nws/bin:/opt/p4/p4-cp-nws/sbin
export RUN_OVS=/opt/p4/p4-cp-nws

ovs-vsctl del-br br-int-1
ovs-vsctl del-br br-int-2

'''+ovs_vxlan+'''
ifconfig br-tun-0 '''+local_br_tun[0]+'''/24 up
ifconfig br-tun-1 '''+local_br_tun[1]+'''/24 up
ip route change 10.1.1.0/24 via '''+remote_br_tun[0]+''' dev br-tun-0
ip route change 11.1.1.0/24 via '''+remote_br_tun[0]+''' dev br-tun-0
ip route change 12.1.1.0/24 via '''+remote_br_tun[0]+''' dev br-tun-0
ip route change 13.1.1.0/24 via '''+remote_br_tun[0]+''' dev br-tun-0
ip route change 14.1.1.0/24 via '''+remote_br_tun[1]+''' dev br-tun-1
ip route change 15.1.1.0/24 via '''+remote_br_tun[1]+''' dev br-tun-1
ip route change 16.1.1.0/24 via '''+remote_br_tun[1]+''' dev br-tun-1
ip route change 17.1.1.0/24 via '''+remote_br_tun[1]+''' dev br-tun-1

sleep 2
ovs-vsctl show

echo "Check the interface configuration"
sleep 1
ip -br a

EOF
'''
    command_list.append(acc_ovs_vxlan)

    file = f'{path}/7_host_vm.sh'
    host_vm = 'cat <<EOF > ./'+file+'''
#!/bin/sh
echo "Setup the Host VMs and VFs"

'''+vf_to_vm+'''

EOF
'''
    command_list.append(host_vm)
    command_list.append(f"chmod +x {path}/*")

    for command in command_list:
        try:
            result = test_setup.ssh_command('host', command)
        except Exception as e:
            print(f"Failed with exception:\n{e}")

    return None


def build_args():
    # Create the top-level parser
    parser = argparse.ArgumentParser(description='Configure Linux Networking with OVS offload with IPv4 transport or VXLAN tunnel')
    subparsers = parser.add_subparsers(dest='command')
    # Create the parser for the "create_script" command
    parser_create_script = subparsers.add_parser('create_script', help='Generate configuration scripts in localhost')
    # Create the parser for the "copy_script" command
    parser_copy_script = subparsers.add_parser('copy_script', help='Generate and copy configuration scripts to IMC and ACC')
    # Create the parser for the "setup" command and add subparser for tunnel and transport mode
    parser_setup = subparsers.add_parser('setup', help='Setup OVS offload with IPv4 transport or VXLAN tunnel, prerequisite: run copy_script option once for scripts to be available in ACC')
    setup_subparsers = parser_setup.add_subparsers(dest='mode')
    # Create the subparser for the "setup" command for transport mode
    setup_subparsers.add_parser('transport', help='Setup OVS offload with IPv4 transport, prerequisite: run copy_script option once for scripts to be available in ACC')
    # Create the subparser for the "setup" command for tunnel mode
    setup_subparsers.add_parser('tunnel', help='Setup OVS offload with VXLAN tunnel, prerequisite: run copy_script option once for scripts to be available in ACC')
    # Create the parser for the "teardown" command
    parser_teardown = subparsers.add_parser('teardown', help='Teardown and cleanup the OVS offload configuration, prerequisite: run copy_script option once for scripts to be available in ACC')
    return parser, parser_setup


if __name__ == "__main__":
    test_setup = TestSetup(config_file = f'{os.path.dirname(os.path.abspath(__file__))}/config.yaml')
    host_path = test_setup.test_config['test_params']['host_path']
    imc_path = test_setup.test_config['test_params']['imc_path']
    acc_path = test_setup.test_config['test_params']['acc_path']
    ip_list = test_setup.test_config['test_params']['ip_list']
    imc_ip = test_setup.test_config['imc']['ssh']['ip']
    acc_ip = test_setup.test_config['acc']['ssh']['ip']
    acc_p4_path = f'{acc_path}/fxp-net_linux-networking'
    lp_interfaces = test_setup.test_config['host']['lp_interfaces']
    lp_interface_ip = test_setup.test_config['host']['lp_interface_ip']
    host_password = test_setup.test_config['host']['ssh']['password']
    imc_login = f'ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@{imc_ip}'
    acc_login = f'ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@{acc_ip}'

    parser, parser_setup = build_args()
    # Parse the arguments
    args = parser.parse_args()

    # Execute the appropriate function based on the subcommand
    if args.command == 'create_script':
        print("\n----------------Create OVS OFFLOAD scripts----------------")
        build_p4rt_config(test_setup = test_setup)

    elif args.command == 'copy_script':
        print("\n----------------Create OVS OFFLOAD scripts----------------")
        build_p4rt_config(test_setup = test_setup)
        print("\n----------------Copy OVS OFFLOAD scripts to the ACC----------------")
        test_setup.copy_scripts()

    elif args.command == 'setup':
        if args.mode is None:
            parser_setup.print_help()
            sys.exit()

        if len(host_password) == 0:
            print("Enter correct IPU Host SSH root password in config.yaml and retry")
            sys.exit()

        print("\n----------------Setup Linux Networking with OVS OFFLOAD----------------")

        # Setup a TMUX session, Login to ACC and start infrap4d
        print("\n----------------Setup TMUX Session, Login to ACC----------------")
        infrap4d = tmux_term(test_setup=test_setup, tmux_name="test1_infrap4d",tmux_override=True)
        result = infrap4d.tmux_send_keys(imc_login, delay=2, output=True)
        result = infrap4d.tmux_send_keys(acc_login, delay=2, output=True)

        print("\n----------------Copy Infrap4d Configuration file----------------")
        result = infrap4d.tmux_send_keys(f'yes | cp -f {acc_path}/{host_path}/es2k_skip_p4.conf {acc_path}/fxp-net_linux-networking/', delay=2, output=True)
        print(result)
        result = infrap4d.tmux_send_keys(f'cd {acc_path}/{host_path}', delay=2, output=True)
        result = infrap4d.tmux_send_keys('ls -lrt', delay=2, output=True)

        print("\n----------------Start Infrap4d, wait for initialization to complete----------------")
        result = infrap4d.tmux_send_keys('./2_acc_infrap4d.sh', delay=180, output=True)
        print(result)

        # Setup a TMUX session, Login to ACC, configure p4rt rules and ovs bridges
        print("\n----------------Setup TMUX Session, Login to ACC----------------")
        p4rt = tmux_term(test_setup=test_setup, tmux_name="test2_p4rt",tmux_override=True)
        result = p4rt.tmux_send_keys(imc_login, delay=2)
        result = p4rt.tmux_send_keys(acc_login, delay=2)
        result = p4rt.tmux_send_keys(f'cd {acc_path}/{host_path}', delay=2, output=True)

        print("\n----------------Use p4rt-ctl to Add the rules----------------")
        result = p4rt.tmux_send_keys('./3_acc_p4rt.sh', delay=60, output=True)
        print(result)
        print("\n----------------Use p4rt-ctl to Dump the rules----------------")
        result = p4rt.tmux_send_keys('./4_acc_p4rt_dump.sh', delay=20, output=True)
        print(result)

        print("\n----------------Setup OVS Environment on the ACC----------------")
        result = p4rt.tmux_send_keys('./5_acc_setup_ovs.sh', delay=10, output=True)
        print(result)

        if args.mode == 'transport':
            print("\n----------------Configure OVS Bridges on ACC in IPv4 transport mode----------------")
            result = p4rt.tmux_send_keys('./6_acc_ovs_bridge.sh', delay=10, output=True)
            print(result)

        if args.mode == 'tunnel':
            print("\n----------------Configure OVS Bridges on ACC in VXLAN tunnel mode----------------")
            result = p4rt.tmux_send_keys('./acc_ovs_vxlan.sh', delay=10, output=True)
            print(result)


        # Setup a TMUX session for the IPU host, configure the VMs, idpf interfaces, Link partner interfaces and run ping checks
        print("\n----------------Setup TMUX Session and Login to the Host----------------")
        host = tmux_term(test_setup=test_setup, tmux_name="test3_host",tmux_override=True)
        result = host.tmux_send_keys(f'cd {host_path}', delay=2, output=True)
        result = host.tmux_send_keys('sudo -s', delay=2, output=True)
        result = host.tmux_send_keys(f'{host_password}', delay=2, output=True)

        print("\n----------------Configure the VMs on the Host and ADD the IDPF SR-IOV VFs----------------")
        result = host.tmux_send_keys('ls -lrt', delay=2, output=True)
        print(f'{result}')
        result = host.tmux_send_keys('./7_host_vm.sh', delay=30, output=True)
        print(result)

        if lp_interfaces:
            print("\n---------------- All-in-one setup: IPU and Link Partner connected to localhost ----------------")
            print("\n---------------- Configure the Link Partner Interfaces in localhost ----------------")
            for idx in range(len(lp_interfaces)):
                result = host.tmux_send_keys(f'ip a a dev {lp_interfaces[idx]} {lp_interface_ip[idx]}/24', delay=3, output=True)
            result = host.tmux_send_keys('ip -br a', delay=3, output=True)
            print(result)

            print("\n---------------- PING TEST : Link partner interface to VM IDPF VF interface in localhost ----------------")
            print(f"\nLINK Partner Interface IP : {lp_interface_ip}")
            print(f"\nHost VM IDPF VF Interface IP : {ip_list}\n")
            for ip in ip_list:
                ping_test(dst_ip=ip, count=4)
        else:
            print("\n---------------- Back-to-back setup: configure Link Partner in remote host----------------")
        print("\n----------------OVS Offload setup in IPU ACC and VM configuration completed in localhost----------------")

    elif args.command == 'teardown':

        if len(host_password) == 0:
            print("Enter correct IPU Host root password in config.yaml and retry")
            sys.exit()

        print("\n----------------Teardown Linux Networking with OVS OFFLOAD----------------")

        print("\n----------------Setup TMUX Session and Login to the Host----------------")
        host = tmux_term(test_setup=test_setup, tmux_name="test3_host",tmux_override=True)
        result = host.tmux_send_keys(f'cd {host_path}', delay=2, output=True)
        result = host.tmux_send_keys('sudo -s', delay=2, output=True)
        result = host.tmux_send_keys(f'{host_password}', delay=2, output=True)

        print("\n----------------Delete the VMs on the Host----------------")
        result = host.tmux_send_keys('ls -lrt', delay=2, output=True)
        print(f'{result}')
        command = '''ip netns del VM0
ip netns del VM1
ip netns del VM2
ip netns del VM3
ip netns del VM4
ip netns del VM5
ip netns del VM6
ip netns del VM7
'''
        result = host.tmux_send_keys(command, delay=10, output=True)
        print(result)
        for idx in range(len(lp_interfaces)):
            result = host.tmux_send_keys(f'ip a d dev {lp_interfaces[idx]} {lp_interface_ip[idx]}/24', delay=3, output=True)
        result = host.tmux_send_keys('ip -br a', delay=3, output=True)
        print(result)

        print("\n----------------Setup TMUX Session, Login to ACC----------------")
        p4rt = tmux_term(test_setup=test_setup, tmux_name="test2_p4rt",tmux_override=True)
        result = p4rt.tmux_send_keys(imc_login, delay=2)
        result = p4rt.tmux_send_keys(acc_login, delay=2)
        result = p4rt.tmux_send_keys(f'cd {acc_path}/{host_path}', delay=2, output=True)

        print("\n----------------Cleanup OVS Bridge Configuration----------------")
        command = f'''export SDE_INSTALL=/opt/p4/p4sde
export P4CP_INSTALL=/opt/p4/p4-cp-nws
export DEPEND_INSTALL=$P4CP_INSTALL
export PATH=/root/.local/bin:/root/bin:/usr/share/Modules/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/opt/p4/p4-cp-nws/bin:/opt/p4/p4-cp-nws/sbin
export RUN_OVS=/opt/p4/p4-cp-nws

ovs-vsctl show
ovs-vsctl del-br br-int-1
ovs-vsctl del-br br-int-2
ovs-vsctl del-br br-tun-0
ovs-vsctl del-br br-tun-1

ip link del TEP0
ovs-vsctl del-br br0
ip link del TEP1
ovs-vsctl del-br br1
ip link del TEP2
ovs-vsctl del-br br2
ip link del TEP3
ovs-vsctl del-br br3
ip link del TEP4
ovs-vsctl del-br br4
ip link del TEP5
ovs-vsctl del-br br5
ip link del TEP6
ovs-vsctl del-br br6
ip link del TEP7
ovs-vsctl del-br br7
ovs-vsctl show
'''
        result = p4rt.tmux_send_keys(command, delay=20, output=True)
        print(result)

        print("\n----------------Use p4rt-ctl to Delete the rules----------------")
        result = p4rt.tmux_send_keys('./acc_p4rt_delete.sh', delay=60, output=True)
        print(result)
        print("\n----------------Use p4rt-ctl to Dump the rules after cleanup----------------")
        result = p4rt.tmux_send_keys('./4_acc_p4rt_dump.sh', delay=30, output=True)
        print(result)

        print("\n----------------Stop Infrap4d on the ACC----------------")
        infrap4d = tmux_term(test_setup=test_setup, tmux_name="test1_infrap4d",tmux_override=True)
        result = infrap4d.tmux_send_keys(imc_login, delay=2, output=True)
        result = infrap4d.tmux_send_keys(acc_login, delay=2, output=True)
        result = infrap4d.tmux_send_keys('ps -aux | grep infrap4d', delay=2, output=True)
        print(result)

    else:
        parser.print_help()

