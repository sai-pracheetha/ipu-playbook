import argparse
import logging
import re
import os

# Configure logging to write logs to a file
log = logging.getLogger()
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s      %(funcName)s.%(filename)s:%(lineno)d %(message)s')

class CliParams:
    def __init__(self):
        self.args = None
        pass

    def get_input_params(self):
        parser = argparse.ArgumentParser(description="Get Cli Params")
        parser.add_argument("--test_config", action="store", required=True, help="test_config_path")
        parser.add_argument("--topology_config", action="store", required=True, help="topology_config_path")

        self.args = parser.parse_args()
        return vars(self.args) 

def get_acc_mac_vsi(ces_base,acc_iface):
    acc_ssh=ces_base.get_def_acc_ssh()
    lines = acc_ssh.exec_command("ifconfig {} | grep ether".format(acc_iface))
    log.info(lines)
    print("get_acc_mac_vsi=",lines)
    acc_mac = lines[0].split()[1]
    print("acc_mac:",acc_mac)

    #get acc vsi
    imc=ces_base.get_def_imc_ssh()
    lines = imc.exec_command("cli_client -q -c | grep {}".format(acc_mac))
    for line in lines:
        if not re.match("fn_id",line):
            continue
        fields = line.split()
        #print("fields=",fields)
        mac = fields[-1]
        if mac == acc_mac:

            acc_vsi = fields[7]

            print("acc_vsi=",acc_vsi)
            break
    return acc_mac,acc_vsi
    
def test_prepare(ces_base):
    acc_ssh=ces_base.get_def_acc_ssh()

    #copy the tdishell that support to run tdi script
    #this help to run tdi by ssh
    tdi_shell_path = f"{os.getcwd()}/workloads/p4/common/tdishell"
    log.info(tdi_shell_path)
    acc_ssh.put_file(tdi_shell_path,"/opt/p4/p4sde/bin/tdishell")
    acc_ssh.exec_command("chmod 777 /opt/p4/p4sde/bin/tdishell")

    #check if need untar p4.tar.gz
    acc_ssh.exec_command("cd /opt;[ -d p4 ] && echo 1 || tar xzvf p4.tar.gz > /dev/null 2>&1")
