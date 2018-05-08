#!/usr/bin/python
# coding=utf-8
import os
import sys
lib_path=os.getcwd()+"/lib"
sys.path.append(lib_path)
import commands
import time
from flask import Flask
from flask import jsonify
from flask import request
import cx_Oracle
# os.environ['NLS_LANG'] = 'SIMPLIFIED CHINESE_CHINA.UTF8'


setting_file=os.getcwd()+"/setting"
ora_user='system'
ora_passwd='abc123'
ora_host='127.0.0.1'
ora_port='1521'
ora_sid='orcl'

app = Flask(__name__)

@app.route('/sysinfo',methods=['GET'])
def sysinfo():
    if request.method == 'GET':
        result = sys_per_info()
        return jsonify(result)

@app.route('/dmesginfo',methods=['GET'])
def dmesginfo():
    if request.method == 'GET':
        num = request.args.get('num')
        if num and int(num)<100000:
            result = perfor_dmesg(num=num)
        else:
            result = perfor_dmesg(num=10)
        return jsonify(result)

@app.route('/oracleinfo',methods=['GET'])
def oracleinfo():
    if request.method == 'GET':
        sql_info = {}
        db_sql = """select dbid,name,to_char(created,'yyyymmdd') created,log_mode,open_mode,database_role,platform_name,flashback_on, force_logging from v$database"""
        sid_sql = """select instance_number,instance_name, version,host_name,to_char(startup_time,'yyyymmdd hh24:mi:ss') startuptime,edition from gv$instance"""
        bak_sql = """SELECT bs.recid, DECODE(backup_type,'L','Archived Redo Logs','D','Datafile Full Backup','I','Incremental Backup') backup_type,
                       device_type,
                       DECODE(bs.controlfile_included, 'NO', '-', bs.controlfile_included) controlfile_included,
                       NVL(sp.spfile_included, '-') spfile_included,
                       bs.incremental_level,
                       TO_CHAR(bs.start_time, 'yyyy-mm-dd HH24:MI:SS') start_time,
                       TO_CHAR(bs.completion_time, 'yyyy-mm-dd HH24:MI:SS') completion_time,
                       round(bs.elapsed_seconds) elapsed_seconds,
                       bp.sizeG sizeG
                  FROM v$backup_set bs,
                       (select  set_stamp, set_count, tag, device_type,round(bytes/1024/1024/1024,2) sizeG
                          from v$backup_piece
                         where status = 'A') bp,
                       (select distinct set_stamp, set_count, 'YES' spfile_included
                          from v$backup_spfile) sp
                 WHERE bs.set_stamp = bp.set_stamp
                   AND bs.set_count = bp.set_count
                   AND bs.set_stamp = sp.set_stamp(+)
                   AND bs.set_count = sp.set_count(+)
                   --And bs.completion_time >= sysdate -3
                 ORDER BY bs.recid
                """
        # sql_info['db'] = connect_db(db_sql)
        sql_info['db'] = connect_db(sid_sql)
        result = sql_info
        return jsonify(result)



def exe_command(exe_cmd):
    (status,output)=commands.getstatusoutput(exe_cmd)
    result={'status':str(status),'info':output}
    return result

def connect_db(sql):
    conn = cx_Oracle.connect(ora_user + '/' + ora_passwd + '@' + ora_sid)
    curs = conn.cursor()
    exe_sql = sql
    curs.execute(exe_sql)
    row = curs.fetchone()
    curs.close()
    conn.close()
    return row


def sys_per_info(pertime=1):
    # pertime = 5
    per_info = {}
    ports = []
    per_info['mem'] = perfor_mem()
    per_info['disk'] = perfor_disk()
    per_info['upinfo'] = perfor_uptime()
    cpu1 = perfor_cpu()
    net1 = perfor_net()
    time.sleep(pertime)
    cpu2 = perfor_cpu()
    net2 = perfor_net()
    per_info['cpu'] = 100-int((cpu2['idel']-cpu1['idel'])/(cpu2['total']-cpu1['total'])*100)
    for one in net1:
        each_port = {'interface': '', 'send_rate': '', 'rev_rate': ''}
        for two in net2:
            if one['interface']== two['interface']:
                each_port['interface'] = two['interface']
                each_port['send_rate'] = str(int((float(two['TransmitBytes']) - float(one['TransmitBytes']))/pertime/1024))
                each_port['rev_rate'] = str(int((float(two['ReceiveBytes']) - float(one['ReceiveBytes']))/pertime/1024))
        ports.append(each_port)
    per_info['net'] = ports
    result = per_info
    return result

def perfor_mem():
    mem_cmd = "cat /proc/meminfo"
    mem_result = exe_command(mem_cmd)
    mem = {}
    if mem_result['status'] == "0" and mem_result['info']:
        for line in mem_result['info'].split('\n'):
            eachitem_mem = line.split(':')
            if len(eachitem_mem) >= 2:
                mem[eachitem_mem[0]] = eachitem_mem[1].split()[0]
    mem['usage'] = str(int((float(mem['MemTotal'])-float(mem['MemFree'])-float(mem['Cached'])-float(mem['Buffers']))/float(mem['MemTotal'])*100))
    result = mem
    return result

def perfor_net():
    net_cmd = "cat /proc/net/dev"
    net_result = exe_command(net_cmd)
    ports = []
    if net_result['status'] == "0" and net_result['info']:
        for line in net_result['info'].split('\n')[2:]:
            eachitem_net = line.split()
            port_info = {'interface': '', 'ReceiveBytes': '', 'TransmitBytes': ''}
            port_info['interface'] = eachitem_net[0].lstrip(":")
            port_info['ReceiveBytes'] = eachitem_net[1]
            port_info['TransmitBytes'] = eachitem_net[9]
            ports.append(port_info)
    result = ports
    return result

def perfor_cpu():
    cpu_cmd = """cat /proc/stat |awk '/cpu /{print $5,$2+$3+$4+$5+$6+$7+$8}'"""
    cpu_result = exe_command(cpu_cmd)
    cpu ={}
    if cpu_result['status'] == "0" and cpu_result['info']:
        cpu['idel'] = float(cpu_result['info'].split()[0])
        cpu['total'] = float(cpu_result['info'].split()[1])
    result = cpu
    return result

def perfor_disk():
    disk_cmd = """df -h |awk '$1!~/Filesystem/{print $1,$2,$5}'"""
    disk_result = exe_command(disk_cmd)
    disk = {'name':'','size':'','used':''}
    disks = []
    if disk_result['status'] == "0":
        for line in disk_result['info'].split('\n'):
            if len(line.split()) ==3:
                disk['name'] = line.split()[0]
                disk['size'] = line.split()[1]
                disk['used'] = line.split()[2]
            disks.append(disk)
            disk = {'name': '', 'size': '', 'used': ''}
    result = disks
    return  result

def perfor_uptime():
    up_cmd = """df -h |awk '$1!~/Filesystem/{print $1,$2,$5}'"""
    up_result = exe_command(up_cmd)
    up_info = {'time': '', 'users': '', 'load': ''}
    if up_result['status'] == "0":
        line = up_result['info']
        if len(line.split('load average:')) == 2:
            up_info['load'] = line.split('load average:')[1]
            up_info['users'] = line.split('load average:')[0].split(',')[1]
            up_info['users'] = line.split('load average:')[0].split(',')[0]
    result = up_info
    return result


def perfor_dmesg(num=1000):
    dmesg_cmd = "dmesg |tail -n "+str(num)
    dmesg_result = exe_command(dmesg_cmd)
    dmesg_info = []
    if dmesg_result['status'] == "0":
        for line in dmesg_result['info'].split('\n'):
            dmesg_info.append(line)
    result =  dmesg_info
    return result


if __name__ == '__main__':
    app.run(host='0.0.0.0',port=6011,threaded=True)
