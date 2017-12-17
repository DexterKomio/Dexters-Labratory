from ts3plugin import ts3plugin

import ts3lib, ts3defines
import os

from PythonQt.QtNetwork import QLocalServer
from PythonQt.QtCore import QByteArray

class ipcdata(object):
    longlen = 5

    def __init__(self, *, init=None, obj=None):
        self.buf = init if init else bytes()
        self.pos = 0

        if obj:
            self.append(obj)

    def append(self, obj):
        if type(obj) is str:
            d = bytes(obj, 'utf-8')
            self.buf += b's'
            self.buf += len(d).to_bytes(self.longlen, byteorder='big')
            self.buf += d
        elif type(obj) is int:
            self.buf += b'i'
            self.buf += obj.to_bytes(self.longlen, byteorder='big', signed=True)
        elif type(obj) is list or type(obj) is tuple:
            self.buf += b'l' if type(obj) is list else b't'
            self.buf += len(obj).to_bytes(self.longlen, byteorder='big')
            for e in obj:
                self.append(e)
        elif obj is None:
            self.buf += b'n'
        else:
            raise Exception("Unknown ipcdata type")

    def read(self):
        t = chr(self.buf[self.pos])
        self.pos += 1

        if t == "s":
            self.pos += self.longlen
            l = int.from_bytes(self.buf[self.pos - self.longlen:self.pos], byteorder='big')
            spos = self.pos
            self.pos += l
            return self.buf[spos:self.pos].decode('utf-8')
        elif t == "i":
            self.pos += self.longlen
            return int.from_bytes(self.buf[self.pos - self.longlen:self.pos], byteorder='big', signed=True)
        elif t == "l" or t == "t":
            ret = []
            self.pos += self.longlen
            l = int.from_bytes(self.buf[self.pos - self.longlen:self.pos], byteorder='big')

            for i in range(l):
                ret.append(self.read())

            return ret if t == "l" else tuple(ret)
        elif t == "n":
            return None
        else:
            raise Exception("Unknown ipcdata type")

    def readAll(self, fromstart=False):
        if fromstart:
            self.pos = 0

        while not self.atEnd():
            yield self.read()

    def atEnd(self):
        return self.pos == len(self.buf)

    @property
    def data(self):
        return self.buf

    def __iadd__(self, other):
        self.append(other)
        return self


class ipcplugin(ts3plugin):
    requestAutoload = False
    name = "ipc"
    version = "1.0.2"
    apiVersion = 21
    author = "Thomas \"PLuS\" Pathmann"
    description = "This is a plugin used for interprocess communication. It broadcasts events to clients and can receive commands to execute."
    offersConfigure = False
    commandKeyword = ""
    infoTitle = None
    menuItems = []
    hotkeys = []

    def __init__(self):
        self.clients = {}
        self.buf = {}

        self.server = QLocalServer()
        self.server.connect("newConnection()", self.onNewConnection)

        path = os.path.join(ts3lib.getPluginPath(), "pyTSon", "ipcsocket")
        QLocalServer.removeServer(path)
        if not self.server.listen(path):
            raise Exception("Error opening local socket (%s)" % path)

    def stop(self):
        for cli in list(self.clients):
            cli.disconnectFromServer()
            cli.delete()

        self.buf = {}

        self.server.close()
        self.server.delete()

    def onNewConnection(self):
        cli = self.server.nextPendingConnection()

        self.clients[cli] = "unknown"

        cli.connect("readyRead()", lambda: self.onClientData(cli))
        cli.connect("disconnected()", lambda: self.onClientDisconnected(cli))

    def onClientData(self, cli):
        if self.clients[cli] == "unknown":
            clitype = cli.read(1)

            if clitype == b'f':
                self.clients[cli] = "function"
                self.buf[cli] = bytes()

                if cli.bytesAvailable() == 0:
                    return
            elif clitype == b'c':
                self.clients[cli] = "callback"
                return
            else:
                cli.write(QByteArray("Unknown client type"))
                cli.disconnectFromServer()
                cli.delete()
                return
        elif self.clients[cli] == "callback":
            return

        self.buf[cli] += cli.read(cli.bytesAvailable()).data()
        self.handleBuffer(cli)

    def handleBuffer(self, cli):
        if len(self.buf[cli]) < ipcdata.longlen:
            return

        plen = int.from_bytes(self.buf[cli][:ipcdata.longlen], byteorder='big')
        if len(self.buf[cli]) < plen: #message not complete
            return
        elif len(self.buf[cli]) > plen: #multiple messages
            self.handleFunction(cli, self.buf[cli][ipcdata.longlen:plen +1])
            self.buf[cli] = self.buf[cli][plen +1:]
            self.handleBuffer(cli)
        else: #only one message len(self.buf) == plen
            self.handleFunction(cli, self.buf[cli][ipcdata.longlen:])
            self.buf[cli] = bytes()

    def handleFunction(self, cli, buf):
        data = ipcdata(init=buf)
        name = data.read()

        if hasattr(ts3lib, name):
            args = []
            while not data.atEnd():
                args.append(data.read())

            ret = getattr(ts3lib, name)(*args)

            if ret:
                data = ipcdata(obj=ret)
            else:
                data = ipcdata(obj=tuple())
            cli.write(QByteArray((len(data.data) + ipcdata.longlen).to_bytes(ipcdata.longlen, byteorder='big') + data.data))
        else:
            err = ts3lib.logMessage("Unknown method data %s" % data.data, ts3defines.LogLevel.LogLevel_ERROR, "pyTSon.ipcplugin", 0)
            if err != ts3defines.ERROR_ok:
                print("Unknown method data in ipcplugin: %s" % data.data)

    def onClientDisconnected(self, cli):
        del self.clients[cli]
        if cli in self.buf:
            del self.buf[cli]

    def send(self, bytestr):
        for cli in self.clients:
            if self.clients[cli] == "callback":
                cli.write(QByteArray((len(bytestr) + ipcdata.longlen).to_bytes(ipcdata.longlen, byteorder='big') + bytestr))

    def callback(self, name, *args):
        data = ipcdata(obj=name)

        for p in args:
            data.append(p)

        self.send(data.data)

    def __getattr__(self, name):
return (lambda *args: self.callback(name, *args))