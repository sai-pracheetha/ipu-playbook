# Linux Networking with OVS Offload

## Introduction

- The ovs_offload_lnw.py tool can be used on an host server connected with Intel® Infrastructure Processing Unit via PCIe.
- It is supported on IPU SDK release version >= 1.7.0 and makes use of the P4 package fxp-net_linux-networking.pkg
- It creates the configuration to run the Linux Networking recipe with OVS Offloaded to the IPU ACC.
- It can be used to start infrap4d on the ACC and program using the p4rt runtime rules to configure ACC port representors for the host IDPF interfaces and IPU Physical Port 0 and Port 1.
- It can set up OVS bridges on the ACC using the port representors and configure VM namespaces for the IDPF interfaces on the Host.
- Transport mode: The tool generates the OVS bridge configuration for transport mode with IPv4 encapsulation, use helper script 6_acc_ovs_bridge.sh.
- Tunnel mode: The tool also generates the OVS bridge configuration for tunnel mode with VXLAN encapsulation, use helper script acc_ovs_vxlan.sh. Refer to the VXLAN section below.

## Supported Topologies

### All-in-one configuration

- IPU adapter and a Link Partner NIC is connected to a single host server. Use Default ipu-playbook/ovs_offload/config.yaml
- Host1 IPU Port0 <-----> Host1 Link Partner Port0
- Host1 IPU Port1 <-----> Host1 Link Partner Port1

### Back-to-back configuration

- 2 IPU adapters are connected to two host servers via PCIe and the IPU Physical Ports on the two servers are connected back to back.
- Host1 IPU Port0 <-----> Host2 IPU Port0
- Host1 IPU Port1 <-----> Host2 IPU Port1
- For IPU Host 1 server copy config_host1.yaml to config.yaml.
- For IPU Host 2 server copy config_host2.yaml to config.yaml.

## IPU host test environment setup

Before running the script, make sure `/etc/ssh/sshd_config` contains the line for root user.

```bash
PermitRootLogin yes
```

## Prerequisites

- The host package `intel-ipu-host-components-<version>.<build number>.tar.gz` contains the example IPU P4 source code, the compiled P4 package, and artifacts that can be used to set up the workload on the IMC and ACC.
- The compiled artifacts for P4 `fxp-net_linux-networking` can be found in the location below after you extract the tar package.

```bash
cd intel-ipu-host-components/P4Tools/P4Programs/artifacts/fxp-net_linux-networking

> ls
total 6.2M
-rw-r--r--. 1 admin12 admin12 1.5M Aug 30 10:47 fxp-net_linux-networking_3de1c1f569bb44d69043c2fb3093d079.pkgo
-rw-r--r--. 1 admin12 admin12  46K Sep  3 11:29 p4Info.txt
-rw-r--r--. 1 admin12 admin12 1.4K Sep  3 11:29 entries.json
-rw-r--r--. 1 admin12 admin12 128K Sep  3 11:29 tdi.json
-rw-r--r--. 1 admin12 admin12 639K Sep  3 11:32 context.json
-rw-r--r--. 1 admin12 admin12 949K Sep  3 11:32 fxp-net_linux-networking.s
-rw-r--r--. 1 admin12 admin12 1.5M Sep  3 11:32 fxp-net_linux-networking_12d1caf7e380490b96f1df444b5050af.pkgo
-rw-r--r--. 1 admin12 admin12 1.5M Sep  3 11:32 fxp-net_linux-networking.pkg

```

### 1. IMC setup to load the P4 package

- Load the P4 package `fxp-net_linux-networking.pkg` on the IMC. Refer Section `IPU P4 Quickstart Guide` in the Intel® Infrastructure Processing Unit Software User Guide
- Login to the IPU IMC from the localhost, default IMC IP is `100.0.0.100`

```bash
ssh root@100.0.0.100
```

- Copy the P4 package `fxp-net_linux-networking.pkg` to the IMC /work/scripts/ directory and update script /work/scripts/load_custom_pkg.sh as shown below.
- Reboot the IMC, on IMC bootup the P4 package and node policy configuration will be updated as shown in `/work/scripts/load_custom_pkg.sh`

#### Host 1 IPU IMC

```bash
[root@ipu-imc ~]# cat /work/scripts/load_custom_pkg.sh
#!/bin/sh
CP_INIT_CFG=/etc/dpcp/cfg/cp_init.cfg
echo "Checking for custom package..."
if [ -e /work/scripts/fxp-net_linux-networking.pkg ]; then
    echo "Custom package fxp-net_linux-networking.pkg found. Overriding default package"
    cp  /work/scripts/fxp-net_linux-networking.pkg /etc/dpcp/package/
    rm -rf /etc/dpcp/package/default_pkg.pkg
    ln -s /etc/dpcp/package/fxp-net_linux-networking.pkg /etc/dpcp/package/default_pkg.pkg
    sed -i 's/sem_num_pages = .*;/sem_num_pages = 28;/g' $CP_INIT_CFG
    sed -i 's/lem_num_pages = .*;/lem_num_pages = 32;/g' $CP_INIT_CFG
    sed -i 's/mod_num_pages = .*;/mod_num_pages = 2;/g' $CP_INIT_CFG
    sed -i 's/acc_apf = 4;/acc_apf = 16;/g' $CP_INIT_CFG
else
    echo "No custom package found. Continuing with default package"
fi
```

#### Host 2 IPU IMC

- For two IPU host servers connected back-to-back we modify the default MAC addresses of the IPU interfaces.
- The MAC suffix is updated for the pf_mac_address and vf_mac_address in the default node policy `/etc/dpcp/cfg/cp_init.cfg` in the Host 2 IPU IMC.
- This ensures that there are no MAC address conflicts and the Host 2 IPU adapter interfaces use a different MAC address.

```bash
[root@ipu-imc ~]# cat /work/scripts/load_custom_pkg.sh
#!/bin/sh
CP_INIT_CFG=/etc/dpcp/cfg/cp_init.cfg
echo "Checking for custom package..."
sed -i 's/pf_mac_address = "00:00:00:00:03:14";/pf_mac_address = "00:00:00:00:04:14";/g' $CP_INIT_CFG
sed -i 's/vf_mac_address = "";/vf_mac_address = "00:00:00:00:06:14";/g' $CP_INIT_CFG
if [ -e /work/scripts/fxp-net_linux-networking.pkg ]; then
    echo "Custom package fxp-net_linux-networking.pkg found. Overriding default package"
    cp  /work/scripts/fxp-net_linux-networking.pkg /etc/dpcp/package/
    rm -rf /etc/dpcp/package/default_pkg.pkg
    ln -s /etc/dpcp/package/fxp-net_linux-networking.pkg /etc/dpcp/package/default_pkg.pkg
    sed -i 's/sem_num_pages = .*;/sem_num_pages = 28;/g' $CP_INIT_CFG
    sed -i 's/lem_num_pages = .*;/lem_num_pages = 32;/g' $CP_INIT_CFG
    sed -i 's/mod_num_pages = .*;/mod_num_pages = 2;/g' $CP_INIT_CFG
    sed -i 's/acc_apf = 4;/acc_apf = 16;/g' $CP_INIT_CFG
else
    echo "No custom package found. Continuing with default package"
fi
```

- After IMC reboots, the above script will update the P4 package to `fxp-net_linux-networking.pkg` and the default node policy `/etc/dpcp/cfg/cp_init.cfg`.

```bash
[root@ipu-imc ~]# ls -lrt /etc/dpcp/package/
total 2852
-rw-r--r-- 1 root root 1532240 Jan  1 00:00 fxp-net_linux-networking.pkg
lrwxr-xr-x 1 root root      46 Jan  1 00:00 default_pkg.pkg -> /etc/dpcp/package/fxp-net_linux-networking.pkg
drwxr-xr-x 2 root root    4096 Sep 11  2024 runtime_files
-rw-r--r-- 1 root root 1376720 Sep 11  2024 e2100-default-1.0.30.0.pkg
```

### 2. ACC setup for P4 binaries and artifacts

- Extract /opt/p4.tar.gz in the ACC and copy P4 artifacts for fxp-net_linux-networking to the ACC
- Login to the IPU IMC from the localhost, default IMC IP is `100.0.0.100`

```bash
ssh root@100.0.0.100
```

- IPU ACC is only reachable from the IMC console by default
- Login to ACC from the IMC, default ACC IP is `192.168.0.2`

```bash
[root@ipu-imc ~]# ssh root@192.168.0.2
```

- Extract /opt/p4.tar.gz in the ACC, this package contains the binaries required to setup OVS offload in the ACC

```bash
[root@ipu-acc ~]# cd /opt/
[root@ipu-acc opt]# tar -xvf p4.tar.gz
```

- Copy the P4 artifacts folder `intel-ipu-host-components/P4Tools/P4Programs/artifacts/fxp-net_linux-networking` from the same IPU SDK release version being tested to the IMC and then to the ACC location `/opt/p4/p4sde/p4_test/fxp-net_linux-networking`.

### 3. Host IDPF driver and interface setup

- Extract The host package `intel-ipu-host-components-<version>.<build number>.tar.gz`, this contains the IDPF source and pre-built RPMs for RHEL and Rocky Linux.
- If using some other flavor of Linux, run the following commands as a root user to build the IDPF driver from source
- Make sure the same version of IDPF driver is loaded on the host, IMC and ACC

```bash
cd intel-ipu-host-components/IDPF
tar -xvf idpf-<version>.tar.gz
cd idpf-<version>
make
make install
```

- Load the IDPF Driver and create 8 SR-IOV VFs using the commands below

```bash
sudo -i
rmmod idpf
modprobe idpf
lsmod | grep idpf
modinfo idpf
echo 8 > /sys/class/net/ens5f0/device/sriov_numvfs
```

- Replace `ens5f0` above with the correct host IDPF interface to create 8 SR-IOV VFs on the host.

### 4. Install TMUX tool on the localhost

- The tool uses tmux sessions when running the option setup and option teardown.
- Install TMUX on the host.

```bash
Ubuntu/Debian.
sudo apt-get update && sudo apt-get -y install tmux

Redhat/CentOS and other RHEL Distros.
sudo yum install update && sudo yum -y install tmux

Check after installing.
# tmux --help
usage: tmux [-2CDlNuvV] [-c shell-command] [-f file] [-L socket-name]
            [-S socket-path] [-T features] [command [flags]]
```

## Test Configuration

- The tool uses the config.yaml file to program the rules for OVS Offload on the IPU adapter and configure the IDPF interfaces on the host server.
- The tool can be used in an all-in-one configuration or 2 IPU servers connected back-to-back.
- More information on the configuration below

### All-in-one setup configuration (config.yaml)

- All-in-one configuration IPU adapter and a Link Partner NIC is connected to a single host server. Use Default ipu-playbook/ovs_offload/config.yaml
- Update the file: config.yaml for the specific test setup. Change the management IP, username, and password for IMC and ACC if they are different.
- Update the test_params section as required for the setup with the correct host, IMC and ACC script paths.
- Update the idpf_interface, vf_interfaces in the config if the interface names are different.
- Update lp_interfaces field with the correct Link Partner interface name if the Link Partner NIC is connected to the same host server.

```bash
> cd ipu-playbook/ovs_offload
```

```bash
> cat config.yaml
host:
  ssh:
    ip: 127.0.0.1
    username: root
    # Update the login password for the IPU Host
    password: ""
  # Link Partner interfaces on IPU host - lp_interfaces[0]<->IPU Port0, lp_interfaces[1]<->IPU Port1
  lp_interfaces: ['ens7f1','ens7f0']
  lp_interface_ip: ['10.0.0.30','20.0.0.30']

imc:
  ssh:
    ip: 100.0.0.100
    username: root
    password: ""

acc:
# SSH to ACC from the IMC
  ssh:
    ip: 192.168.0.2
    username: root
    password: ""

test_params:
    #path fields specify the location where the configuration scripts will be copied to on the Host,IMC and ACC
    host_path: 'ovs_offload_lnw_scripts'
    imc_path: '/mnt/imc/p4_test'
    acc_path:  '/opt/p4/p4sde/p4_test'
    # Update the correct IDPF Interface on the Host
    idpf_interface: 'ens5f0'
    # Update the list of Host IDPF Interfaces on the Host to Map to ACC Port representors
    # Interfaces ['0','1'] below represents the IPU Physical Port 0 and Port 1 and the remaining as the Host IDPF Vfs
    vf_interfaces: ['0','1','ens5f0v0','ens5f0v1','ens5f0v2','ens5f0v3','ens5f0v4','ens5f0v5','ens5f0v6','ens5f0v7']
    # These are the ACC Port representors that will be used to map to the interfaces in the above list vf_interfaces
    acc_pr_interfaces:  ['enp0s1f0d4','enp0s1f0d5','enp0s1f0d6','enp0s1f0d7','enp0s1f0d8','enp0s1f0d9','enp0s1f0d10','enp0s1f0d11','enp0s1f0d12','enp0s1f0d13']
    # The ip_list contains the IP addresses that will be used for the Host IDPF VF interfaces that are mapped to the VM config (using: ip netns).
    ip_list: ['10.0.0.10','10.0.0.11','10.0.0.12','10.0.0.13','20.0.0.10','20.0.0.11','20.0.0.12','20.0.0.13']
    # User Input for OVS VXLAN Config.
    # Local and remote vtep(virtual tunnel end-point) IPs are used in OVS vxlan config with ACC PRs mapped to host IDPF VF
    local_vtep: ['10.1.1.1','11.1.1.1','12.1.1.1','13.1.1.1','14.1.1.1','15.1.1.1','16.1.1.1','17.1.1.1','18.1.1.1','19.1.1.1','20.1.1.1']
    remote_vtep: ['10.1.1.2','11.1.1.2','12.1.1.2','13.1.1.2','14.1.1.2','15.1.1.2','16.1.1.2','17.1.1.2','18.1.1.2','19.1.1.2','20.1.1.2']
    # Tunnel Termination Bridge IP for local and remote peer.
    local_br_tun_ip: ['1.1.1.1','2.1.1.1']
    remote_br_tun_ip: ['1.1.1.2','2.1.1.2']
```

### Back-to-back setup configuration for 2 IPU hosts (config_host1.yaml and config_host2.yaml)

- 2 IPU host servers are connected back-to-back.
- Host1 IPU Port0 <-----> Host2 IPU Port0
- Host1 IPU Port1 <-----> Host2 IPU Port1
- Copy config_host1.yaml to IPU Host 1 server and rename file to config.yaml.
- Copy config_host2.yaml to IPU Host 2 server and rename file to config.yaml.
- Run ovs_offload_lnw.py in the 2 IPU host servers after copying the respective configs as above.
- Update the file: config.yaml for the specific test setup. Change the management IP, username, and password for IMC and ACC if they are different.
- Update the test_params section as required for the setup with the correct host, IMC and ACC script paths.
- Update the idpf_interface, vf_interfaces name in the config if the interface names are different.
- Note that the lp_interfaces and lp_interface_ip fields below is empty as we are running in back-to-back mode and there is no Link Partner NIC connected to the same server.

### IPU Host 1

```bash
> cd ipu-playbook/ovs_offload
> cp config_host1.yaml config.yaml
```

```bash
> cat config_host1.yaml
host:
  ssh:
    ip: 127.0.0.1
    username: root
    # Update the login password for the IPU Host
    password: ""
  # Link Partner interfaces on IPU host - lp_interfaces[0]<->IPU Port0, lp_interfaces[1]<->IPU Port1
  lp_interfaces: []
  lp_interface_ip: []

imc:
  ssh:
    ip: 100.0.0.100
    username: root
    password: ""

acc:
# SSH to ACC from the IMC
  ssh:
    ip: 192.168.0.2
    username: root
    password: ""

test_params:
    #path fields specify the location where the configuration scripts will be copied to on the Host,IMC and ACC
    host_path: 'ovs_offload_lnw_scripts'
    imc_path: '/mnt/imc/p4_test'
    acc_path:  '/opt/p4/p4sde/p4_test'
    # Update the correct IDPF Interface on the Host
    idpf_interface: 'ens2f0'
    # Update the list of Host IDPF Interfaces on the Host to Map to ACC Port representors
    # Interfaces ['0','1'] below represents the IPU Physical Port 0 and Port 1 and the remaining as the Host IDPF Vfs
    vf_interfaces: ['0','1','ens2f0v0','ens2f0v1','ens2f0v2','ens2f0v3','ens2f0v4','ens2f0v5','ens2f0v6','ens2f0v7']
    # These are the ACC Port representors that will be used to map to the interfaces in the above list vf_interfaces
    acc_pr_interfaces:  ['enp0s1f0d4','enp0s1f0d5','enp0s1f0d6','enp0s1f0d7','enp0s1f0d8','enp0s1f0d9','enp0s1f0d10','enp0s1f0d11','enp0s1f0d12','enp0s1f0d13']
    # The ip_list contains the IP addresses that will be used for the Host IDPF VF interfaces that are mapped to the VM config (using: ip netns).
    ip_list: ['10.0.0.10','10.0.0.11','10.0.0.12','10.0.0.13','20.0.0.10','20.0.0.11','20.0.0.12','20.0.0.13']
    # User Input for OVS VXLAN Config.
    # Local and remote vtep(virtual tunnel end-point) IPs are used in OVS vxlan config with ACC PRs mapped to host IDPF VF
    local_vtep: ['10.1.1.1','11.1.1.1','12.1.1.1','13.1.1.1','14.1.1.1','15.1.1.1','16.1.1.1','17.1.1.1','18.1.1.1','19.1.1.1','20.1.1.1']
    remote_vtep: ['10.1.1.2','11.1.1.2','12.1.1.2','13.1.1.2','14.1.1.2','15.1.1.2','16.1.1.2','17.1.1.2','18.1.1.2','19.1.1.2','20.1.1.2']
    # Tunnel Termination Bridge IP for local and remote peer.
    local_br_tun_ip: ['1.1.1.1','2.1.1.1']
    remote_br_tun_ip: ['1.1.1.2','2.1.1.2']
```

### IPU Host 2

```bash
> cd ipu-playbook/ovs_offload
> cp config_host2.yaml config.yaml
```

```bash
> cat config_host2.yaml
host:
  ssh:
    ip: 127.0.0.1
    username: root
    # Update the login password for the IPU Host
    password: ""
  # Link Partner interfaces on IPU host - lp_interfaces[0]<->IPU Port0, lp_interfaces[1]<->IPU Port1
  lp_interfaces: []
  lp_interface_ip: []

imc:
  ssh:
    ip: 100.0.0.100
    username: root
    password: ""

acc:
# SSH to ACC from the IMC
  ssh:
    ip: 192.168.0.2
    username: root
    password: ""

test_params:
    #path fields specify the location where the configuration scripts will be copied to on the Host,IMC and ACC
    host_path: 'ovs_offload_lnw_scripts'
    imc_path: '/mnt/imc/p4_test'
    acc_path:  '/opt/p4/p4sde/p4_test'
    # Update the correct IDPF Interface on the Host
    idpf_interface: 'ens2f0'
    # Update the list of Host IDPF Interfaces on the Host to Map to ACC Port representors
    # Interfaces ['0','1'] below represents the IPU Physical Port 0 and Port 1 and the remaining as the Host IDPF Vfs
    vf_interfaces: ['0','1','ens2f0v0','ens2f0v1','ens2f0v2','ens2f0v3','ens2f0v4','ens2f0v5','ens2f0v6','ens2f0v7']
    # These are the ACC Port representors that will be used to map to the interfaces in the above list vf_interfaces
    acc_pr_interfaces:  ['enp0s1f0d4','enp0s1f0d5','enp0s1f0d6','enp0s1f0d7','enp0s1f0d8','enp0s1f0d9','enp0s1f0d10','enp0s1f0d11','enp0s1f0d12','enp0s1f0d13']
    # The ip_list contains the IP addresses that will be used for the Host IDPF VF interfaces that are mapped to the VM config (using: ip netns).
    ip_list: ['10.0.0.20','10.0.0.21','10.0.0.22','10.0.0.23','20.0.0.20','20.0.0.21','20.0.0.22','20.0.0.23']
    # User Input for OVS VXLAN Config.
    # Local and remote vtep(virtual tunnel end-point) IPs are used in OVS vxlan config with ACC PRs mapped to host IDPF VF
    local_vtep: ['10.1.1.2','11.1.1.2','12.1.1.2','13.1.1.2','14.1.1.2','15.1.1.2','16.1.1.2','17.1.1.2','18.1.1.2','19.1.1.2','20.1.1.2']
    remote_vtep: ['10.1.1.1','11.1.1.1','12.1.1.1','13.1.1.1','14.1.1.1','15.1.1.1','16.1.1.1','17.1.1.1','18.1.1.1','19.1.1.1','20.1.1.1']
    # Tunnel Termination Bridge IP for local and remote peer.
    remote_br_tun_ip: ['1.1.1.1','2.1.1.1']
    local_br_tun_ip: ['1.1.1.2','2.1.1.2']
```

## Python environment setup for localhost

### Setup a python virtual environment

```bash
cd ipu-playbook/ovs_offload
python -m venv --copies venv
```

#### Activate the venv and install requirements

```bash
# source venv/bin/activate
(venv)# pip install -r requirements.txt
(venv)# deactivate
```

- requirements.txt

```text
PyYAML
```

- Run the tool **ovs_offload_lnw.py** as a root user.
- Use the python venv to run the tool

```bash
sudo -i
cd ipu-playbook/ovs_offload
source venv/bin/activate
```

## OVS Offload tool supported options

### ovs_offload_lnw.py : (P4:fxp-net_linux-networking.p4, IPU SDK Release >= 1.7.0)

- **ovs_offload/ovs_offload_lnw.py** makes use of **P4 package: fxp-net_linux-networking.pkg** for IPU SDK release 1.7.0 and later
- Refer the prerequisite section in this document before proceeding with script execution

```bash
python ovs_offload_lnw.py
usage: ovs_offload_lnw.py [-h] {create_script,copy_script,setup,teardown} ...

Configure Linux Networking with OVS offload with IPv4 transport or VXLAN tunnel

positional arguments: {create_script,copy_script,setup,teardown}
    create_script       Generate configuration scripts in localhost
    copy_script         Generate and copy configuration scripts to IMC and ACC
    setup               Setup OVS offload with IPv4 transport or VXLAN tunnel, prerequisite: run copy_script option once for scripts to be available
                        in ACC
    teardown            Teardown and cleanup the OVS offload configuration, prerequisite: run copy_script option once for scripts to be available in
                        ACC

optional arguments:
  -h, --help            show this help message and exit
```

### 1. create_script (optional step used for debug)

- This option will create the configuration shell scripts in the localhost script directory
- The localhost script directory path is specified in **host_path** field in **config.yaml**
- Default localhost script directory path is **ipu-playbook/ovs_offload/ovs_offload_lnw_scripts**

```bash
python ovs_offload_lnw.py create_script
```

The helper shell scripts will be created as shown below.

```bash
ls ipu-playbook/ovs_offload/ovs_offload_lnw_scripts
total 60K
-rwxr-xr-x. 1 admin12 admin12 1.6K Aug 28 13:37 es2k_skip_p4.conf
-rwxr-xr-x. 1 admin12 admin12  375 Aug 28 13:37 1_host_idpf.sh
-rwxr-xr-x. 1 admin12 admin12 1.3K Aug 28 13:37 2_acc_infrap4d.sh
-rwxr-xr-x. 1 admin12 admin12  12K Aug 28 13:37 3_acc_p4rt.sh
-rwxr-xr-x. 1 admin12 admin12 8.4K Aug 28 13:37 acc_p4rt_delete.sh
-rwxr-xr-x. 1 admin12 admin12 2.0K Aug 28 13:37 4_acc_p4rt_dump.sh
-rwxr-xr-x. 1 admin12 admin12 1.3K Aug 28 13:37 5_acc_setup_ovs.sh
-rwxr-xr-x. 1 admin12 admin12 2.1K Aug 28 13:37 6_acc_ovs_bridge.sh
-rwxr-xr-x. 1 admin12 admin12 6.1K Aug 28 13:37 acc_ovs_vxlan.sh
-rwxr-xr-x. 1 admin12 admin12 2.8K Aug 28 13:37 7_host_vm.sh
```

### 2. copy_script (execute once to copy the scripts to ACC before running setup or teardown)

- This option will create the configuration shell scripts in the localhost script directory (the path can be changed in **host_path:** in **config.yaml**) default path is **ovs_offload/ovs_offload_lnw_scripts**
- It copies the scripts from localhost to IPU IMC (the path can be changed in **imc_path:** in **config.yaml**) default path is `/mnt/imc/p4_test`)
- It copies the scripts from the IMC to the ACC (the path can be changed in **acc_path:** in **config.yaml**) default path is `/opt/p4/p4sde/p4_test`

```bash
python ovs_offload_lnw.py copy_script
```

### 3. setup

- Configure OVS offload on ACC and setup localhost IDPF VFs with VM namespaces
- Prerequisite: run copy_script option once for scripts to be available in ACC

```bash
python ovs_offload_lnw.py setup
usage: ovs_offload_lnw.py setup [-h] {transport,tunnel} ...

positional arguments: {transport,tunnel}
    transport         Setup OVS offload with IPv4 transport, prerequisite: run copy_script option once for scripts to be available in ACC
    tunnel            Setup OVS offload with VXLAN tunnel, prerequisite: run copy_script option once for scripts to be available in ACC

optional arguments:
  -h, --help          show this help message and exit
```

- setup option supports two modes transport(IPv4) and tunnel(VXLAN)
- This will setup OVS offload on the ACC and configure the VMs on the localhost by creating persistent TMUX sessions.
- Creates TMUX session:test1_infrap4d to launch infrap4d application on the ACC
- Creates TMUX session:test2_p4rt to configure the p4rt-ctl rules, configure OVS bridges on the ACC
- Creates TMUX session:test3_host to create VM namespaces and add the Host IDPF VF interfaces in the localhost.
- Optional - After running the setup option we can login to each of the tmux sessions.

```bash
> tmux ls
test1_infrap4d: 1 windows (created Thu Aug 29 12:35:25 2024)
test2_p4rt: 1 windows (created Thu Aug 29 12:33:26 2024)
test3_host: 1 windows (created Thu Aug 29 12:32:55 2024)
```

Attach to a tmux session

```bash
tmux a -t test2_p4rt
```

Detach from inside a tmux session.

```bash
ctrl+b d
```

### 4. teardown

```bash
python ovs_offload_lnw.py teardown
```

- This option will remove the OVS offload configuration on the ACC and cleanup the localhost VM namespace configs.
- Prerequisite: run copy_script option once for scripts to be available in ACC
- Configure TMUX session - test3_host delete the VMs on Host and remove the link partner configuration.
- Configure TMUX session - test2_p4rt delete the p4rt-ctl rules and delete the OVS bridges
- Configure TMUX session - test1_infrap4d, login to ACC and stop infrap4d,

## OVS Offload setup with automation tool ovs_offload_lnw.py

### OVS Offload Setup IPv4 transport

- Run the commands below in the IPU localhost server to configure OVS Offload on the IPU ACC with IPv4 transport and configure the Host IDPF interfaces and VM namespaces.

```bash
python ovs_offload_lnw.py copy_script
python ovs_offload_lnw.py setup transport
```

### OVS Offload Setup VXLAN tunnel

- Run the commands below in the IPU localhost server to configure OVS Offload on the IPU ACC with VXLAN tunnel and configure the Host IDPF interfaces and VM namespaces.

```bash
python ovs_offload_lnw.py copy_script
python ovs_offload_lnw.py setup tunnel
```

## OVS offload setup manual execution

### 1. IPU P4 Artifacts on ACC

- The script uses the P4 binaries in the ACC at location `/opt/p4/p4-cp-nws`
- The script requires the P4 artifacts to be available in the folder below in the ACC, make sure to copy the correct artifacts for the release. Refer prerequisites section for more information.

```bash
[root@ipu-acc ~]# ls /opt/p4/p4sde/p4_test/fxp-net_linux-networking
```

### 2. Infrap4d Configuration file

- Copy the infrap4d config in **/opt/p4/p4sde/p4_test/ovs_offload_lnw_scripts/es2k_skip_p4.conf** to artifact folder **/opt/p4/p4sde/p4_test/fxp-net_linux-networking** in the ACC

```bash
[root@ipu-acc ~]# cp /opt/p4/p4sde/p4_test/ovs_offload_lnw_scripts/es2k_skip_p4.conf /opt/p4/p4sde/p4_test/fxp-net_linux-networking/
```

### 3. Start Infrap4d

- Use the shell scripts in /opt/p4/p4sde/p4_test/ovs_offload_lnw_scripts in the ACC to set up infrap4d, p4rt and OVS bridge:
- ACC Terminal 1 : Set up environment and start Infrap4d

```bash
[root@ipu-acc ~]# cd /opt/p4/p4sde/p4_test/ovs_offload_lnw_scripts

[root@ipu-acc ovs_offload_lnw_scripts]# ./2_acc_infrap4d.sh
```

Wait for infrap4d to initialize and start listening on the server.

```bash
Initialized lld_cpchnl control path
Fetching VF info
................

ipu_p4d: dev_id 0 initialized
cpfl_set_rx_function(): Using Split Scalar Rx (port 0).
cpfl_set_tx_function(): Using Split Scalar Tx (port 0).
Port 0 MAC: 00 22 00 01 03 20
cpfl_set_rx_function(): Using Split Scalar Rx (port 1).
cpfl_set_tx_function(): Using Split Scalar Tx (port 1).
Port 1 MAC: 00 23 00 02 03 20

ipu_p4d: initialized 1 devices
Skip p4 lib init
ipu_p4d: spawning cli server thread
ipu_p4d: running in background; driver shell is disabled
ipu_p4d: server started - listening on port 9999
E20240414 00:03:48.469659 293611 es2k_hal.cc:276] [secure mode] Stratum external-facing services are listening to 0.0.0.0:9339, 0.0.0.0:9559, localhost:9559...
```

### 4. Configure P4 pipeline and add the ACC Port Representor rules

- ACC Terminal 2 : Configure pipeline and set up runtime rules.

```bash
[root@ipu-acc ovs_offload_lnw_scripts]# pwd
/opt/p4/p4sde/p4_test/ovs_offload_lnw_scripts

[root@ipu-acc ovs_offload_lnw_scripts]# ./3_acc_p4rt.sh
```

- ACC Terminal 2 : Dump the p4rt-ctl runtime rules.

```bash
[root@ipu-acc ovs_offload_lnw_scripts]# pwd
/opt/p4/p4sde/p4_test/ovs_offload_lnw_scripts

[root@ipu-acc ovs_offload_lnw_scripts]# ./4_acc_p4rt_dump.sh
```

### 5. Set up ACC environment for OVS

- ACC Terminal 2 : Set up the OVS Environment.

```bash
[root@ipu-acc ovs_offload_lnw_scripts]# pwd
/opt/p4/p4sde/p4_test/ovs_offload_lnw_scripts

[root@ipu-acc ovs_offload_lnw_scripts]# ./5_acc_setup_ovs.sh
```

### 6. Set up OVS bridge configuration

#### OVS bridges for IPv4 transport

- ACC Terminal 2 : Set up the OVS bridge config for IPv4 transport

```bash
[root@ipu-acc ovs_offload_lnw_scripts]# pwd
/opt/p4/p4sde/p4_test/ovs_offload_lnw_scripts

[root@ipu-acc ovs_offload_lnw_scripts]# ./6_acc_ovs_bridge.sh
```

#### OVS bridges for VXLAN tunnel

- This configuration script will setup OVS VXLAN Bridges.

```bash
[root@ipu-acc ovs_offload_lnw_scripts]# pwd
/opt/p4/p4sde/p4_test/ovs_offload_lnw_scripts

[root@ipu-acc ovs_offload_lnw_scripts]# ./acc_ovs_vxlan.sh
```

- Stop firewalld on IPU Host and the ACC

```bash
systemctl stop firewalld
```

### 7. Set up VM namespaces on the IPU Host

- IPU HOST Terminal 1 : Configure the VMs on the IPU Host the script below uses **ip netns**

```bash
[root@host]# cd ovs_offload/scripts/ovs_offload_lnw_scripts
[root@host]# ./7_host_vm.sh
```

### 8. All-in-one setup link partner configuration

#### All-in-one setup IPv4 transport mode

- configure IP to the Link Partner interface in localhost and Test Ping to the Host IDPF VF interfaces in the VMs.

```bash
# Link Partner connected to IPU Port 0
sudo ip a a dev ens7f1 10.0.0.30/24

# Link Partner connected to IPU Port 1
sudo ip a a dev ens7f0 20.0.0.30/24

# Test Ping LP(IPU Port 0) <-> VM0(IDPF SRIOV VF)
ip netns exec VM0 ip -br a
ping 10.0.0.10
ip netns exec VM0 ping 10.0.0.30

# Test Ping LP(IPU Port 1) <-> VM4(IDPF SRIOV VF)
ip netns exec VM4 ip -br a
ping 20.0.0.10
ip netns exec VM4 ping 20.0.0.30
```

#### All-in-one setup VXLAN tunnel mode

- Run simple script below to configure 1 VXLAN tunnel on the Link Partner Connected to Port 0

```bash
 #!/bin/sh

echo "Set up Tunnel End Point and the Vxlan config on the Link Partner on remote host"
echo "Add HOST VF ens5f0v0 to the VM0 namespace"
ip link del dev TEP10
ip link del dev vxlan10

echo ""
echo "Configure the Remote Tunnel End Point TEP10"
ip link add dev TEP10 type dummy
ifconfig TEP10 10.1.1.2/24 up
sleep 1
ip addr show TEP10

echo ""
echo "Configure the VXLAN Interface vxlan10"
ip link del vxlan10
ip link add vxlan10 type vxlan id 10 dstport 4789 remote 10.1.1.1 local 10.1.1.2
ip addr add 10.0.0.30/24 dev vxlan10
ip link set vxlan10 up
sleep 1
ip addr show vxlan10

echo ""
echo "Configure the Link Partner interface Connected to Port 0"
ip addr del dev ens7f1 10.0.0.30/24
ifconfig ens7f1 1.1.1.2/24 up
ip route change 10.1.1.0/24 via 1.1.1.1 dev ens7f1
sleep 1
ip addr show ens7f1

echo "Verify the Configure interfaces"
```

#### Run a Ping Test

```bash
[root@host ovs_offload_lnw_scripts]# ip netns exec VM0 ip -br a
lo               DOWN
ens5f0v0         UP             10.0.0.10/24 fe80::21a:ff:fe00:314/64

[root@host ovs_offload_lnw_scripts]# ip -br a
lo               UNKNOWN        127.0.0.1/8 ::1/128
eno8303          UP             10.232.27.29/23 fe80::c6cb:e1ff:fea7:3c82/64
eno8403          UP             100.0.0.1/24
ens7f0           UP
ens7f1           UP             1.1.1.2/24
ens5f0           UP
ens5f0d1         UP
ens5f0d2         UP
ens5f0d3         UP
TEP10            UNKNOWN        10.1.1.2/24 fe80::fcf2:f4ff:fe2a:18f4/64
vxlan10          UNKNOWN        10.0.0.30/24 fe80::7c76:4ff:fe03:8591/64

[root@host ovs_offload_lnw_scripts]# ip netns exec VM0 ping 10.0.0.30
PING 10.0.0.30 (10.0.0.30) 56(84) bytes of data.
64 bytes from 10.0.0.30: icmp_seq=1 ttl=64 time=0.072 ms
64 bytes from 10.0.0.30: icmp_seq=2 ttl=64 time=0.047 ms
64 bytes from 10.0.0.30: icmp_seq=3 ttl=64 time=0.041 ms
^C
--- 10.0.0.30 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2028ms
rtt min/avg/max/mdev = 0.041/0.053/0.072/0.013 ms

[root@host ovs_offload_lnw_scripts]# ping 10.0.0.10
PING 10.0.0.10 (10.0.0.10) 56(84) bytes of data.
64 bytes from 10.0.0.10: icmp_seq=1 ttl=64 time=0.058 ms
64 bytes from 10.0.0.10: icmp_seq=2 ttl=64 time=0.046 ms
64 bytes from 10.0.0.10: icmp_seq=3 ttl=64 time=0.040 ms
^C
--- 10.0.0.10 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2050ms
rtt min/avg/max/mdev = 0.040/0.048/0.058/0.007 ms
```

### OVS Offload configuration with VXLAN tunnel on two IPU host servers connected back-to-back

- Ideally OVS Offload with VXLAN can be run with 2 IPU Peer Setups connected back to back.
- Run python script **ovs_offload_lnw.py copy_script** as a root user on the 2 peer IPU Hosts to generate the configuration.
- Host1 IPU Port0 <-----> Host2 IPU Port0
- Host1 IPU Port1 <-----> Host2 IPU Port1
- For IPU Host 1 server copy config_host1.yaml to config.yaml.

#### Update the config.yaml for OVS VXLAN for IPU 1 Setup

- For IPU Host 1 server copy config_host1.yaml to config.yaml.

```bash
> cat config.yaml
test_params:
....
    # The ip_list contains the IP addresses that will be used for the Host IDPF VF interfaces that are mapped to the VM config (using: ip netns).
    ip_list: ['10.0.0.10','10.0.0.11','10.0.0.12','10.0.0.13','20.0.0.10','20.0.0.11','20.0.0.12','20.0.0.13']
    # User Input for OVS VXLAN Config.
    # Local and remote vtep(virtual tunnel end-point) IPs are used in OVS vxlan config with ACC PRs mapped to host IDPF VF
    local_vtep: ['10.1.1.1','11.1.1.1','12.1.1.1','13.1.1.1','14.1.1.1','15.1.1.1','16.1.1.1','17.1.1.1','18.1.1.1','19.1.1.1','20.1.1.1']
    remote_vtep: ['10.1.1.2','11.1.1.2','12.1.1.2','13.1.1.2','14.1.1.2','15.1.1.2','16.1.1.2','17.1.1.2','18.1.1.2','19.1.1.2','20.1.1.2']
    # Tunnel Termination Bridge IP for local and remote peer.
    local_br_tun_ip: ['1.1.1.1','2.1.1.1']
    remote_br_tun_ip: ['1.1.1.2','2.1.1.2']
```

#### Update config.yaml for OVS VXLAN Config for IPU 2 Setup

- For IPU Host 2 server copy config_host2.yaml to config.yaml.

```bash
> cat config.yaml
test_params:
....
    # The ip_list contains the IP addresses that will be used for the Host IDPF VF interfaces that are mapped to the VM config (using: ip netns).
    ip_list: ['10.0.0.20','10.0.0.21','10.0.0.22','10.0.0.23','20.0.0.20','20.0.0.21','20.0.0.22','20.0.0.23']
    # User Input for OVS VXLAN Config.
    # Local and remote vtep(virtual tunnel end-point) IPs are used in OVS vxlan config with ACC PRs mapped to host IDPF VF
    local_vtep: ['10.1.1.2','11.1.1.2','12.1.1.2','13.1.1.2','14.1.1.2','15.1.1.2','16.1.1.2','17.1.1.2','18.1.1.2','19.1.1.2','20.1.1.2']
    remote_vtep: ['10.1.1.1','11.1.1.1','12.1.1.1','13.1.1.1','14.1.1.1','15.1.1.1','16.1.1.1','17.1.1.1','18.1.1.1','19.1.1.1','20.1.1.1']
    # Tunnel Termination Bridge IP for local and remote peer.
    local_br_tun_ip: ['1.1.1.2','2.1.1.2']
    remote_br_tun_ip: ['1.1.1.1','2.1.1.1']
```

- Follow the instructions provided in previous sections to setup infrap4d, p4rt-ctl and OVS on both the IPU Peer setups.
- VXLAN tunnels are setup between IPU1 VM0 to IPU2 VM0, IPU1 VM1 to IPU2 VM1, ..., IPU1 VM7 to IPU2 VM7
- Ping from VM0 on IPU 1 Host to VM0 on IPU 2 Host should be successful. similarly ping between other VMs like VM1 IPU1 to VM1 IPU2 and so on

## OVS Offload teardown with automation tool ovs_offload_lnw.py

- Run the tool with option **teardown**

```bash
> python ovs_offload_lnw.py teardown
```

## OVS Offload teardown manual execution

### 1. IPU HOST Terminal: Delete the VMs created on the IPU Host

```bash
ip netns del VM0
ip netns del VM1
ip netns del VM2
ip netns del VM3
ip netns del VM4
ip netns del VM5
ip netns del VM6
ip netns del VM7
```

### 2. ACC Terminal: Delete the OVS Bridge Config on the ACC

```bash
#!/bin/sh
export SDE_INSTALL=/opt/p4/p4sde
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
```

### 3. ACC Terminal: Delete the p4rt-ctl runtime rules

```bash
[root@ipu-acc ovs_offload_lnw_scripts]# pwd
/opt/p4/p4sde/p4_test/ovs_offload_lnw_scripts

[root@ipu-acc ovs_offload_lnw_scripts]# ./acc_p4rt_delete.sh

[root@ipu-acc ovs_offload_lnw_scripts]# ./4_acc_p4rt_dump.sh
```

### 4. ACC Terminal: Terminate the infrap4d

- If infrap4d is running in current ACC terminal

```bash
[root@ipu-acc ~]# ctrl + c
```

- Kill the infrap4d process

```bash
[root@ipu-acc ~]# ps -aux | grep infrap4d
root       11120  0.0  0.0   4392  3156 pts/0    S+   00:45   0:00 /bin/sh ./2_acc_infrap4d.sh
root       11188  0.4  0.5 70305376 81572 pts/0  SLl+ 00:45   1:00 /opt/p4/p4-cp-nws/sbin/infrap4d --nodetach
root       24663  0.0  0.0   3620  1732 pts/1    S+   04:24   0:00 grep --color=auto infrap4d

[root@ipu-acc ~]# kill 11188
```

## Appendix

- For IPU SDK version < 1.6.1 use below scripts

### ovs_offload_lnw_v3.py: (P4:fxp-net_linux-networking_v3.p4, IPU SDK Release 1.6.0, 1.6.1)

- This is a python script: **ovs_offload/ovs_offload_lnw_v3.py** that can be used with **P4: fxp-net_linux-networking_v3.p4** for release 1.6.0,1.6.1

```bash
> python ovs_offload_lnw_v3.py
usage: ovs_offload_lnw_v3.py [-h] {create_script,copy_script,setup,teardown} ...

Run Linux networking V3 with OVS Offload

positional arguments:
  {create_script,copy_script,setup,teardown}
                        options
    create_script       Generate configuration scripts in localhost
    copy_script         Copy configuration scripts to IMC and ACC
    setup               Setup the complete OVS offload Recipe, prerequisite: run copy_script option once for
                        scripts to be available in ACC
    teardown            Teardown the complete OVS offload Recipe, prerequisite: run copy_script option once
                        for scripts to be available in ACC

optional arguments:
  -h, --help            show this help message and exit
```

### ovs_offload_lnw_v2.py: (P4:fxp-net_linux-networking_v2.p4, IPU SDK Release 1.4.0)

- This is a python script: **ovs_offload/scripts/ovs_offload_lnw_v2.py** that can be used with **P4: fxp-net_linux-networking_v2.p4** for release 1.4.0

```bash
> python ovs_offload_lnw_v2.py
usage: ovs_offload_lnw_v2.py [-h] {create_script,copy_script,setup,teardown} ...

Run Linux networking V2 with OVS Offload

positional arguments:
  {create_script,copy_script,setup,teardown}
                        options
    create_script       Generate configuration scripts in localhost
    copy_script         Copy configuration scripts to IMC and ACC
    setup               Setup the complete OVS offload Recipe, prerequisite: run copy_script option once for
                        scripts to be available in ACC
    teardown            Teardown the complete OVS offload Recipe, prerequisite: run copy_script option once
                        for scripts to be available in ACC

optional arguments:
  -h, --help            show this help message and exit
```
