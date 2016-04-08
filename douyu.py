'''
Created on 2016-01-12
@author: solomonlu(mengyi.lu)
@mail:52169479@qq.com
'''
import os
import json
import time
import argparse
import re
import socket
import struct
import uuid
import hashlib
import signal
import threading
from urllib import unquote


url = 'http://www.douyutv.com/'
server_list_config_file_location = "ServerListConfig.conf"
server_config_searcher = re.compile('"server_config":"[%\w\.]+"')


def getServerList():
    server_config_all = []
    if os.path.exists(server_list_config_file_location):
        file = open(server_list_config_file_location,"r")
        temp_server_config_all = file.readlines()
        file.close()

        for server in temp_server_config_all:
            server_config_all.append(server.strip())

    return server_config_all

def contentToNetworMsg(content):
    content_length = len(content)
    msg_length = 4 + 4 + content_length + 1
    magic_code = 0x2b1
    return struct.pack("<3i"+str(content_length)+"sb", msg_length,msg_length,magic_code,content,0)

def networkMsgToContent(msg):
    msg_length, = struct.unpack("<i", msg[:4])
    content_length = int(msg_length) - 4 - 4 - 1
    (a,a,a,content,a) = struct.unpack("<3i"+str(content_length)+"sb", msg)
    return content
     
def sendLoginReq(socket,room,debug):
    devid = str(uuid.uuid4()).replace("-","").upper()
    rt = str(int(time.time()))

    m = hashlib.md5()
    m.update(rt + "7oE9nPEG9xXV69phU31FYCLUagKeYtsF" + devid)
    vk = m.hexdigest()

    ver = "20150929"

    content = "type@=loginreq/username@=/ct@=2/password@=/roomid@=" + str(room) + "/devid@=" + devid + "/rt@=" + rt + "/vk@=" + vk + "/ver@=" + ver + "/"
    if debug:
        print "send:" + content
    msg = contentToNetworMsg(content)

    socket.sendall(msg)

def sendHeartBeatReq(socket,room,debug):
    rt = str(int(time.time()))

    m = hashlib.md5()
    m.update(rt + "7oE9nPEG9xXV69phU31FYCLUagKeYtsF")
    k = m.hexdigest()

    content = "type@=keeplive/tick@=" + rt + "/vbw=0/k@=" + k
    if debug:
        print "send:" + content
    msg = contentToNetworMsg(content)

    socket.sendall(msg)

def searchDanmuServer(room):
    import requests
    room_url = url + str(room)
    r = requests.get(room_url)
    html_content = r.text.encode('utf-8')

    m = server_config_searcher.search(html_content)
   
    if m:
        server_config = m.group(0).split(":")[1].strip('"')
        server_config = unquote(server_config)
        server_list = json.loads(server_config)
        return server_list
    else:
        print "can't find server config!"
        return None


def startScanDanmuServer(room):
    server_config_all = getServerList()

    while(True):
        print ("scan for server list...")

        server_list_config_file_handler = open(server_list_config_file_location,"a")
            
        new_server_config = []
        server_list = searchDanmuServer(room)
        for server in server_list:
            server_config = ("%s:%s")%(server["ip"],server["port"])
            if not server_config in server_config_all:
                print "find new server:[%s]"%server_config
                server_config_all.append(server_config)
                new_server_config.append(server_config + "\n")

        server_list_config_file_handler.writelines(new_server_config)
        server_list_config_file_handler.close()

        print ("sleep 10 sec...\n")
        time.sleep(10)


class ThreadImpl(threading.Thread):
    def __init__(self, room, host, port):
        threading.Thread.__init__(self)
        self._room = room
        self._host = host
        self._port = port
  
    def run(self):
        print threading.currentThread().getName() + " start!"
        
        s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)    
        err = s.connect((self._host,self._port))
    
        if (err != None):
            print "connect %s:%d failed!" % (host,port)
            s.close()
            return

        sendLoginReq(s,self._room,False)

        msg = s.recv(1024)
        content = networkMsgToContent(msg)

        global is_sigint_up
        while(not is_sigint_up):
            sendHeartBeatReq(s,self._room,False)
            time.sleep(45)

        s.close()
        print threading.currentThread().getName() + " stop!"



def startLogin(room,debug):
    server_config_all = getServerList()

    if debug:
        host = server_config_all[0].split(":")[0]
        port = int(server_config_all[0].split(":")[1])
        print host,port

        s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)    
        err = s.connect((host,port))
    
        if (err != None):
            print "connect %s:%d failed!" % (host,port)
            s.close()
            return

        sendLoginReq(s,room,True)

        msg = s.recv(1024)
        content = networkMsgToContent(msg)
        print "recv:" + content

        try:
            while(True):
                sendHeartBeatReq(s,room,True)
                time.sleep(45)
        except IOError:
            pass
        finally:
            s.close()
    else:
        for server in server_config_all:
            host = server.split(":")[0]
            port = int(server.split(":")[1])
            print host,port

            threads = []
            for x in xrange(10):
                threads.append(ThreadImpl(room,host,port))
            for t in threads:
                t.start()
                time.sleep(1)

            time.sleep(10)

        try:
            while(True):
                time.sleep(60)
        except IOError:
            pass


def sigint_handler(signum, frame):
    global is_sigint_up
    is_sigint_up = True
    print 'catched interrupt signal!'
    print "!!! wait for threads stop.DON'T DO ANYTHING !!!"


if __name__ == "__main__":
    is_sigint_up = False
    signal.signal(signal.SIGINT, sigint_handler)

    parser = argparse.ArgumentParser(description='douyu helper tools.')
    parser.add_argument("-r","--room", help="room id",type=int,dest="room",required=True)
    parser.add_argument("--debug", help="only for login",action="store_true", dest="debug", default=False)
    parser.add_argument("cmd",choices=['search','login'],help="cmd type")
    args = parser.parse_args()

    if args.cmd == "search":
        startScanDanmuServer(args.room)
    elif args.cmd == "login":
        startLogin(args.room,args.debug)

