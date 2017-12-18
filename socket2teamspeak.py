from ts3plugin import ts3plugin

import ts3lib, ts3defines
import socket, threading

class threadedSocket(object):
    def __init__(self, host, port):
	    ts3lib.logMessage('Initializing...',ts3defines.LogLevel.LogLevel_ERROR,"pyTSon.socket2teamspeak",0)
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))

    def listen(self):
        self.sock.listen(5)
        while True:
            client, address = self.sock.accept()
            client.settimeout(60)
            threading.Thread(target = self.listenToClient,args = (client,address)).start()

    def listenToClient(self, client, address):
        size = 1024
        while True:
            try:
                data = client.recv(size)
                if data:
                    # Set the response to echo back the recieved data 
                    response = data
                    ts3lib.logMessage(data,ts3defines.LogLevel.LogLevel_ERROR,"pyTSon.socket2teamspeak",0)
                    client.send(response)
                else:
                	ts3lib.logMessage('Client disconnected',ts3defines.LogLevel.LogLevel_ERROR,"pyTSon.socket2teamspeak",0)
                    raise error('Client disconnected')
            except:
                client.close()
                return False

class ipcplugin(ts3plugin):
    requestAutoload = True
    name = "socket2teamspeak"
    version = "0.0.1"
    apiVersion = 21
    author = "Ash \"Dexter\" Pesante"
    description = "Provides a socket for external application support."
    offersConfigure = False # TODO: Implement Config Window.
    commandKeyword = "socket2ts"
    infoTitle = None
    menuItems = []
    hotkeys = []
    
    def __init__(self):
    	# Logging for fun.

    	self.server = threadedSocket('127.0.0.1', 12345)


    def stop(self):
    	# TODO: Stop stuff.
		self.server.stop()
