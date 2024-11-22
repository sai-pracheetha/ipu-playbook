# IPsec Acceleration Scripts

## Introduction

- The ipsec_accel.py script can be used on an host server connected with Intel® Infrastructure Processing Unit via PCIe.
- It creates the configuration to run the Linux Networking Recipe with IPsec Acceleration.
- It can be used to start infrap4d on the ACC and use the script generated p4rt-ctl rules to configure ACC Port representors for the Host IDPF interfaces and IPU Physical Ports.
- It can set up OVS bridges on the ACC using the port representors and configure the IDPF and VF interfaces on the Host.
- It can setup IPsec tunnel/transport mode.
- The steps menitoned here are for MEV back to back connected setup. Follow these steps in both hosts.

## Test Environment Setup

Before running the script, make sure `/etc/ssh/ssd_config` contains the line.

```bash
PermitRootLogin yes
```

### Prerequisites

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

- Load the P4 package `fxp-net_linux-networking.pkg` on the IMC. Refer section 'Load the P4 pacakge` in `IPDK IPsec (tunnel/transport mode) with strongSwan running on the Host` in `Crytographic Features` in the Intel® Infrastructure Processing Unit Software User Guide. Additionally on Host 2 need to change MAC in node policy config file. Add the following line in load_custom_pkg.sh after the sed commands in Host 2. 

```bash
On Host 2

sed -i 's/00:00:00:00:03:14/00:00:00:00:22:01/g' $CP_INIT_CFG

Reboot the IMC

```

- Copy the P4 artifacts folder for the specific release version being tested to the IMC and then to the ACC location `/opt/fxp-net_linux-networking`.
- Make sure the same version of IDPF driver is loaded on the Host, IMC and ACC, run commands below as a root user

```bash
sudo -i
modprobe idpf
lsmod | grep idpf
modinfo idpf
echo 8 > /sys/class/net/ens5f0/device/sriov_numvfs
```

- Replace `ens5f0` above with the correct Host IDPF Interface to create 8 SR-IOV VFs on the Host.
- Build strongSwan on host. Follow the instructions in section `strongSwan Build on Host` in `IPDK IPsec (tunnel/transport mode) with strongSwan running on the Host` in `Crytographic Features` in the Intel® Infrastructure Processing Unit Software User Guide.
- The tool uses tmux sessions when running the option setup and option teardown.
- Install TMUX on the IPU Host.

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

### Test Topology
![Topology](https://github.com/user-attachments/assets/2a568b9a-93f0-4b4b-b672-644f6bb52d1f)

### Test Configuration (config.yaml)

- The following configurations can be run in MEV back to back connected setup.
- There are two config yaml files : config_host1.yaml and config_host2.yaml. On host 1 rename config_host1.yaml to config.yaml. On host 2 rename config_host2.yaml to config.yaml. Update the file config.yaml for the specific test setup. Change the management IP, username, and password for imc and acc if they are different.
- Update the test_params section as required for the setup with the correct host, imc and acc script paths.
- Update the idpf_interface, vf_interfaces, local_vxlan_tunnel_mac, remote_vxlan_ip, remote_vxlan_mac on both hosts configs.
- comm_ip_host, comm_ip_acc are the IPs configured on host and ACC respectively for establishing communication channel between them.
- local_vxlan_tunnel_mac is the MAC of V0 interface based on the config_host1.yaml.
- remote_vxlan_ip is the IP on remote host. In this example it is 192.168.1.102.
- remote_vxlan_mac is the MAC of V0 interface on remote host based on the config_host2.yaml 
 

```bash
> cd ipu-playbook/ipsec_accel
```

```bash
> cat config.yaml
host:
  ssh:
    ip: 10.232.27.15
    username: admin12
    # Update the login password for the IPU Host
    password: "password"

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
    host_path: 'ipsec_accel_scripts'
    imc_path: '/mnt/imc/p4_test'
    acc_path:  '/opt/'
    # Update the correct IDPF Interface on the Host
    idpf_interface: 'ens5f0'
    # IPs for communication channel between host and ACC
    comm_ip_host: '10.10.0.1'
    comm_ip_acc: '10.10.0.2'
    # Update the list of Host IDPF Interfaces on the Host to Map to ACC Port representors
    # Interfaces ['0','1'] below represents the IPU Physical Port 0 and Port 1 and the remaining as the Host IDPF Vfs
    vf_interfaces: ['0','ens5f0v0','ens5f0v1']
    # These are the ACC Port representors that will be used to map to the interfaces in the above list vf_interfaces. The last PR will be for IPsec application.
    acc_pr_interfaces:  ['enp0s1f0d4','enp0s1f0d5','enp0s1f0d6']
    # The ip_list contains the IP addresses that will be used for the Host IDPF VF interfaces that are mapped to the VM config (using: ip netns). The last IP is for IPsec application
    ip_list: ['192.168.1.101','11.0.0.1']
    # Host VF MAC and remote LP MAC
    local_vxlan_tunnel_mac: ['00:1a:00:00:03:14']
    # Remote vxlan IP
    remote_vxlan_ip: ['192.168.1.102']
    remote_vxlan_mac: ['00:1a:00:00:22:01']
    # User Input for OVS VXLAN Config.
    # Local and remote vtep(virtual tunnel end-point) IPs are used in OVS vxlan config with ACC PRs mapped to host IDPF VF
    local_vtep: ['10.1.1.1']
    remote_vtep: ['10.1.1.2']
    # Tunnel Termination Bridge IP for local and remote peer.
    local_br_tun_ip: ['1.1.1.1']
    remote_br_tun_ip: ['1.1.1.2']
    #Directory where strongswan is built on the host
    strongSwan_build: '/home/admin12/ipsec/ipsec_combined_sep16/ipsec-recipe/'
    #Host 1 or Host 2
    ipsec_host: '1'
```

## Python Environment Setup

Use python venv:

```bash
cd ipu-playbook
python -m venv --copies venv
```

Activate the venv and install requirements:

```bash
# source venv/bin/activate
(venv)# pip install -r requirements.txt
(venv)# deactivate
```

### requirements.txt

```text
PyYAML
```

Run python script **ipsec_accel.py** as a root user.

```bash
sudo -i
cd ipu-playbook
source venv/bin/activate
cd ipsec_accel
```

## Test Script

### ipsec_accel.py : (P4:fxp-net_linux-networking.p4, IPU SDK Release >= 1.8.0)

1. This is a python script : **ipsec_accel/ipsec_accel.py** that can be used with **P4: fxp-net_linux-networking.p4** for release 1.7.0 and later.

    ```bash
    > python ipsec_accel.py
    usage: ipsec_accel.py [-h] {create_script,copy_script,setup,ipsec_transport,ipsec_tunnel,teardown} ...

    Run Linux networking with IPsec Acceleration

    positional arguments:
       {create_script,copy_script,setup,ipsec_transport,ipsec_tunnel,teardown}
                           options
       create_script       Generate configuration scripts in localhost
       copy_script         Copy configuration scripts to IMC and ACC
       setup               Setup the complete OVS offload Recipe, prerequisite: run copy_script option once for scripts to be available in ACC
       ipsec_transport     Setup the IPsec configs for transport mode, prerequisite: run copy_script option once for scripts to be available in Host
       ipsec_tunnel        Setup the IPsec configs for tunnel mode, prerequisite: run copy_script option once for scripts to be available in Host & ACC
       teardown            Teardown the IPsec Acceleration Recipe, prerequisite: run copy_script option once for scripts to be available in ACC

    optional arguments:
      -h, --help            show this help message and exit

    ```

2. create_script: This will create the configuration scripts in the script directory (the path can be changed in **host_path** in **config.yaml**) at **ipsec_accel/ipsec_accel_scripts/**
   If host 1, copy config_host1.yaml to config.yaml. If host 2,  config_host2.yaml to config.yaml. Change the configs according to your setup.

    ```bash
    > python ipsec_accel.py create_script
    ```

    The scripts will be created as shown below.

    ```bash
    > ls ipsec_accel/ipsec_accel_scripts/
    total 96
    -rwxr-xr-x 1 admin12 admin12 1806 Oct 28 23:19 es2k_skip_p4.conf
    -rwxr-xr-x 1 admin12 admin12  417 Oct 28 23:19 1_host_idpf.sh
    -rwxr-xr-x 1 admin12 admin12  189 Oct 28 23:19 setup_host_comm_channel.sh
    -rwxr-xr-x 1 admin12 admin12  219 Oct 28 23:19 setup_acc_comm_channel.sh
    -rwxr-xr-x 1 admin12 admin12  460 Oct 28 23:19 sync_host_acc_date.sh
    -rwxr-xr-x 1 admin12 admin12  153 Oct 28 23:19 generate_certs.sh
    -rwxr-xr-x 1 admin12 admin12  271 Oct 28 23:19 copy_certs.sh
    -rwxr-xr-x 1 admin12 admin12 1166 Oct 28 23:19 2_acc_infrap4d.sh
    -rwxr-xr-x 1 admin12 admin12 5362 Oct 28 23:19 3_acc_p4rt.sh
    -rwxr-xr-x 1 admin12 admin12 3709 Oct 28 23:19 acc_p4rt_delete.sh
    -rwxr-xr-x 1 admin12 admin12  592 Oct 28 23:19 4_acc_p4rt_dump.sh
    -rwxr-xr-x 1 admin12 admin12 1288 Oct 28 23:19 5_acc_setup_ovs.sh
    -rwxr-xr-x 1 admin12 admin12 1100 Oct 28 23:19 6_acc_ovs_bridge.sh
    -rwxr-xr-x 1 root    root     502 Oct 28 23:19 proxy.sh
    -rwxr-xr-x 1 admin12 admin12  942 Oct 28 23:19 host_ipsec_config.sh
    -rwxr-xr-x 1 admin12 admin12  484 Oct 28 23:19 ipsec.conf_transport_1
    -rwxr-xr-x 1 admin12 admin12  647 Oct 28 23:19 ipsec.conf_tunnel_1
    -rwxr-xr-x 1 admin12 admin12  482 Oct 28 23:19 ipsec.conf_transport_2
    -rwxr-xr-x 1 root    root     645 Oct 28 23:19 ipsec.conf_tunnel_2
    -rwxr-xr-x 1 admin12 admin12 1892 Oct 28 23:19 ipsec_tunnel_config.sh
    -rwxr-xr-x 1 admin12 admin12   67 Oct 28 23:19 ipsec.secrets
    -rwxr-xr-x 1 admin12 admin12 1421 Oct 28 23:19 acc_ovs_vxlan.sh
    -rwxr-xr-x 1 admin12 admin12  204 Oct 28 23:19 7_host_vm.sh
    ```

3. copy_script: This will create the configuration scripts in the script directory (the path can be changed in **host_path** in **config.yaml**) at **ipsec_accel/ipsec_accel_scripts** and also copy it to the ACC to the acc_path field provided in the **config file:config.yaml**

    ```bash
    > python ipsec_accel.py copy_script
    ```

4. setup:

    ```bash
    > python ipsec_accel.py setup
    ```

    - This will setup the OVS networking.
    - Configure TMUX session - test_host_comm, configures host comm channel, sync date between host and ACC, copies certificates.
    - Configure TMUX session - test_acc_comm, configures ACC comm channel, generates certifcates.
    - Configure TMUX session - test_infrap4d, login to ACC and launch infrap4d,
    - Configure TMUX session - test_p4rt configure the p4rt-ctl rules, configure OVS bridges
    - Configure TMUX session - test3_host configure the VFs on Host IDPF interface.
    - Run a ping test to check the forwarding.
    - After running the setup option we can login to each of the tmux sessions.

    > tmux ls
    test_acc_comm
    test_host_comm
    test_infrap4d
    test_p4rt
    test3_host
    
    ```

    Attach to a tmux session

    ```bash
    tmux a -t test_p4rt
    ```

    Detach from inside a tmux session.

    ```bash
    ctrl+b d
    ```

5. ipsec_tranport:

    ```bash
    > python ipsec_accel.py ipsec_transport
    ```
    - This will setup transport mode.
    - Prerequisite: run create_script, copy_script and setup.
    - Configures TMUX session - test_host_ipsec 
    - Attach to this TMUX session : tmux a -t test_host_ipsec
    - Execute './ipsec start' on both ends to establish IPsec Transport mode.
    - Check for SADB counters in IMC : 'cli_client -qsS' and encrypted/decrypted counters increment.
    - Execute './ipsec stop' to stop the IPsec session.


6. ipsec_tunnel

    ```bash
    > python ipsec_accel.py ipsec_tunnel
    ```
    - This will setup tunnel mode.
    - Prerequisite: run create_script, copy_script and setup.
    - Configures TMUX session - test_host_ipsec
    - Attach to this TMUX session : 'tmux a -t test_host_ipsec'
    - Execute './ipsec start' on both ends to establish IPsec Tunnel mode.
    - Check for SADB counters in IMC : 'cli_client -qsS' and encrypted/decrypted counters increment.
    - Execute './ipsec stop' to stop the IPsec session.


7. teardown:

    ```bash
    > python ipsec_accel.py teardown
    ```

    - This will tear down the complete OVS setup.
    - Prerequisite: run copy_script option once for scripts to be available in ACC
    - Configure TMUX session - test_p4rt delete the p4rt-ctl rules and delete the OVS bridges
    - Configure TMUX session - test_infrap4d, login to ACC and stop infrap4d,






## Use the Scripts on the Host and ACC to Setup IPsec Acceleration

- Following needs to be done on both hosts
- Follow the instructions below to run the recipe on the ACC with the help of configuration scripts which got genereated via create_script and copy_script or
- Run the tool with setup followed by ipsec_transport/ipsec_tunnel option.

```bash
> python ipsec_accel.py setup
> python ipsec_accel.py ipsec_tranpsort
> python ipsec_accel.py ipsec_tunnel
```

### 1. IPU P4 Artifacts on ACC

- The scripts expects the P4 artifacts to be available in the folder below in the ACC. Make sure to copy the correct artifacts for the release.

```bash
[root@ipu-acc ~]# ls /opt/fxp-net_linux-networking
```


### 2. Setup Host to ACC Communication Channel

```bash

On Host
host# cd ipsec_accel/ipsec_accel_scripts
host# ./setup_host_comm_channel.sh
```


```bash

On ACC

acc# cd /opt/ipsec_accel_scripts
acc# ./setup_acc_comm_channel.sh
```

### 3. Sync date between Host and ACC

```bash

On Host

host# ipsec_accel/ipsec_accel_scripts
host# ./sync_host_acc_date.sh

```


### 4. Generate certificates in ACC


```bash

On ACC

acc# cd /opt/ipsec_accel_scripts
acc# ./generate_certs.sh

```
 

### 5. Copy certificates to Host

```bash

On Host

host# ipsec_accel/ipsec_accel_scripts
host# ./copy_certs.sh

```


### 6. Infrap4d Configuration file

Copy the infrap4d config in **/opt/ipsec_accel_scripts/es2k_skip_p4.conf** to artifact folder **/opt/fxp-net_linux-networking** in the ACC

```bash

On ACC
acc# cp /opt/ipsec_accel_scripts/es2k_skip_p4.conf /opt/fxp-net_linux-networking/
```

### 7. Start Infrap4d

- Use the ipsec_accel_scripts in the ACC to set up infrap4d, p4rt and OVS bridge:

```bash
acc# cd /opt/ipsec_accel_scripts

acc# ./2_acc_infrap4d.sh
```

Wait 30 seconds for infrap4d to initialize and start listening on the server.


### 8. Configure P4 pipeline and add the ACC PR rules


```bash
acc# cd /opt/ipsec_accel_scripts

acc# ./3_acc_p4rt.sh
```


```bash
acc# cd /opt/ipsec_accel_scripts

acc# ./4_acc_p4rt_dump.sh
```

### 9. Set up ACC environment for OVS


```bash
acc# cd /opt/ipsec_accel_scripts

acc# ./5_acc_setup_ovs.sh
```

### 10. Set up OVS Bridge Configuration


```bash
acc# cd /opt/ipsec_accel_scripts

acc# ./acc_ovs_vxlan.sh
```

### 11. Set up VF interfaces configuration on the IPU Host 


```bash
host]# cd ipsec_accel/ipsec_accel_scripts
host]# ./7_host_vm.sh
```


Run a Ping Test to Host 2

```bash

host# ip -br a
lo               UNKNOWN        127.0.0.1/8 ::1/128
eno8303          UP             10.232.27.15/23 fe80::c6cb:e1ff:fea7:3c9c/64
eno8403          UP             100.0.0.1/24
ens7f0           DOWN
ens7f1           DOWN
docker0          DOWN           172.17.0.1/16
ens5f0           UP
ens5f0d1         UP
ens5f0d2         UP             10.10.0.1/24
ens5f0d3         UP
ens5f0v0         UP             192.168.1.101/24
ens5f0v1         UP             11.0.0.1/24
ens5f0v2         UP
ens5f0v7         UP
ens5f0v6         UP
ens5f0v5         UP
ens5f0v3         UP
ens5f0v4         UP

host# ping 192.168.1.102
PING 192.168.1.102 (192.168.1.102) 56(84) bytes of data.
64 bytes from 192.168.1.102: icmp_seq=1 ttl=64 time=1107 ms
64 bytes from 192.168.1.102: icmp_seq=2 ttl=64 time=107 ms
64 bytes from 192.168.1.102: icmp_seq=3 ttl=64 time=0.344 ms
64 bytes from 192.168.1.102: icmp_seq=4 ttl=64 time=0.317 ms
^C
--- 192.168.1.102 ping statistics ---
4 packets transmitted, 4 received, 0% packet loss, time 3048ms
rtt min/avg/max/mdev = 0.317/303.674/1107.126/465.909 ms, pipe 2

```


### 11. Set up IPsec transport mode 

```bash


host# cd ipsec_accel/ipsec_accel_scripts
host# ./host_ipsec_config.sh
host# source proxy.sh
host# yes|cp -f ipsec.secrets {strongSwan_build}/ipsec_offload_plugin/output_strongswan/etc/


Host 1
host1# yes|cp -f ipsec.conf_transport_1 {strongSwan_build}/ipsec_offload_plugin/output_strongswan/etc/ipsec.conf


Host 2
host2# yes|cp -f ipsec.conf_transport_2 {strongSwan_build}/ipsec_offload_plugin/output_strongswan/etc/ipsec.conf


```

In the same terminal as above execute ipsec application on both hosts.

```bash

host# cd {strongSwan_build}
host# source env_setup_acc.sh

host# cd {strongSwan_build}/ipsec_offload_plugin/output_strongswan/usr/sbin
host# ./ipsec start

```

In the same terminal Check for IPsec status 

```bash
host# cd {strongSwan_build}/ipsec_offload_plugin/output_strongswan/usr/sbin
host# ./ipsec status

[root@Aurora sbin]# ./ipsec status
Security Associations (1 up, 0 connecting):
    sts-base[1]: ESTABLISHED 3 minutes ago, 192.168.1.101[192.168.1.101]...192.168.1.102[192.168.1.102]
    sts-base{1}:  INSTALLED, TRANSPORT, reqid 1, ESP SPIs: 4f000001_i 93000001_o
    sts-base{1}:   192.168.1.101/32[tcp] === 192.168.1.102/32[tcp]

```

Send traffic and check for SADB counters in IMC

```bash

Host 1

host1# ssh admin12@192.168.1.102

[root@Aurora sbin]# ssh admin12@192.168.1.102
admin12@192.168.1.102's password:
Activate the web console with: systemctl enable --now cockpit.socket

Last login: Tue Oct 29 05:54:02 2024 from 192.168.1.101
[admin12@Hestia ~]$


IMC

imc : cli_client -qsS


[root@ipu-imc ~]# cli_client -qsS
No IP address specified, defaulting to localhost
ipsec rx dec packets: 16 bytes: 3221
ipsec rx replay errors: 0
ipsec rx auth failures: 0
ipsec rx misc errors: 0
ipsec rx bad pkts: 0
ipsec tx enc packets: 18 bytes: 2825
ipsec tx misc errors: 0
ipsec tx bad pkts: 0
cisp rx dec packets: 0 bytes: 0
cisp rx auth failures: 0
cisp rx misc errors: 0
cisp rx bad pkts: 0
cisp tx enc packets: 0 bytes: 0
cisp tx misc errors: 0
cisp tx bad pkts: 0


```



### 12. Set up IPsec tunnel mode


```bash
On ACC

acc# cd /opt/ipsec_accel_scripts
acc# ./ipsec_tunnel_config.sh
```


```bash
On Host

host# cd ipsec_accel/ipsec_accel_scripts
host# ./host_ipsec_config.sh
host# source proxy.sh
host# yes|cp -f ipsec.secrets {strongSwan_build}/ipsec_offload_plugin/output_strongswan/etc/


Host 1
host1# yes|cp -f ipsec.conf_tunnel_1 {strongSwan_build}/ipsec_offload_plugin/output_strongswan/etc/ipsec.conf


Host 2
host2# yes|cp -f ipsec.conf_tunnel_2 {strongSwan_build}/ipsec_offload_plugin/output_strongswan/etc/ipsec.conf


```

In the same terminal as above execute ipsec application on both hosts.

```bash

host# cd {strongSwan_build}
host# source env_setup_acc.sh

host# cd {strongSwan_build}/ipsec_offload_plugin/output_strongswan/usr/sbin
host# ./ipsec start

```

In the same terminal check for IPsec status

```bash
host# cd {strongSwan_build}/ipsec_offload_plugin/output_strongswan/usr/sbin
host# ./ipsec status

[root@Aurora sbin]# ./ipsec status
Security Associations (1 up, 0 connecting):
    sts-base[1]: ESTABLISHED 37 seconds ago, 192.168.1.101[192.168.1.101]...192.168.1.102[192.168.1.102]
    sts-base{1}:  INSTALLED, TUNNEL, reqid 1, ESP SPIs: 6d000001_i 5a000001_o
    sts-base{1}:   11.0.0.1/32[tcp] === 11.0.0.2/32[tcp]
(venv) [root@Aurora sbin]#


```

Send traffic and check for SADB counters in IMC

```bash

Host

(venv) [root@Aurora sbin]# ssh admin12@11.0.0.2
admin12@11.0.0.2's password:
Activate the web console with: systemctl enable --now cockpit.socket

Last login: Tue Oct 29 06:22:23 2024 from 11.0.0.1
[admin12@Hestia ~]$ 


IMC

[root@ipu-imc ~]# cli_client -qsS
No IP address specified, defaulting to localhost
ipsec rx dec packets: 80 bytes: 12759
ipsec rx replay errors: 0
ipsec rx auth failures: 0
ipsec rx misc errors: 0
ipsec rx bad pkts: 0
ipsec tx enc packets: 125 bytes: 12867
ipsec tx misc errors: 2
ipsec tx bad pkts: 0
cisp rx dec packets: 0 bytes: 0
cisp rx auth failures: 0
cisp rx misc errors: 0
cisp rx bad pkts: 0
cisp tx enc packets: 0 bytes: 0
cisp tx misc errors: 0
cisp tx bad pkts: 0

server finished responding =======================

```


Stop IPsec application

```bash
host# ./ipsec stop
```
### Optional:  Clean up the configs

Run the tool with option **teardown**

```bash
> python ipsec_accel.py teardown
```

ACC Terminal  : Delete the OVS Bridge Config on the ACC

```bash
#!/bin/sh
export SDE_INSTALL=/opt/p4/p4sde
export P4CP_INSTALL=/opt/p4/p4-cp-nws
export DEPEND_INSTALL=$P4CP_INSTALL
export PATH=/root/.local/bin:/root/bin:/usr/share/Modules/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/opt/p4/p4-cp-nws/bin:/opt/p4/p4-cp-nws/sbin
export RUN_OVS=/opt/p4/p4-cp-nws

ovs-vsctl show
ovs-vsctl del-br br-int-0
ovs-vsctl del-br br-tun-0

ip link del TEP0
ovs-vsctl del-br br0

```

ACC Terminal : Delete the p4rt-ctl runtime rules

```bash
acc# cd /opt/ipsec_accel_scripts

acc# ./acc_p4rt_delete.sh

acc# ./4_acc_p4rt_dump.sh
```
