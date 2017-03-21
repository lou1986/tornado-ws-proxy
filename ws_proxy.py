import tornado
import tornado.websocket
import tornado.iostream
import socket
import sys
import optparse

class TCPClient(object):
	def __init__(self, host, port, client=None):
		self.host = host
		self.port = port
		self.stream = None
		self.sock_fd = None
		self.client = client

	def connect(self):
		self.sock_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
		self.stream = tornado.iostream.IOStream(self.sock_fd)
		self.stream.set_close_callback(self.on_close)
		self.stream.connect((self.host, self.port), self.read)

	def on_receive(self, data):
		self.stream.read_bytes(1024, streaming_callback=self.on_streaming, callback=self.on_receive)

	def on_streaming(self, data):
		self.client.write_message(data, binary=True)

	def read(self):
		self.stream.read_bytes(1024, streaming_callback=self.on_streaming, callback=self.on_receive)

	def on_close(self):
		if self.client:
			self.client.close()
		print 'closed'

	def write(self, msg):
		self.stream.write(msg)

	def close(self):
		self.stream.close()

class WsProxy(tornado.websocket.WebSocketHandler):
	clients = set()
	stream_map = {}

	def check_origin(self, origin):
		return True

	def open(self):
		WsProxy.clients.add(self)
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
		global proxy_ip, proxy_port
		c = TCPClient(proxy_ip, proxy_port, client=self)
		WsProxy.stream_map[self] = c
		c.connect()

	def on_message(self, message):
		st = WsProxy.stream_map[self]
		st.write(message)

	def on_close(self):
		WsProxy.clients.remove(self)
		if WsProxy.stream_map.get(self):
			st = WsProxy.stream_map[self]
			st.close()
			del WsProxy.stream_map[self]

if __name__ == '__main__':
	usage = "\npython %prog --lport lport --rhost ip:rport"
	parser = optparse.OptionParser(usage=usage)
	parser.add_option("--lport", type=int, default=8999, help="port to listen for connections on.")
	parser.add_option("--rhost", help="address to forward the connection to.")
	(opts, args) = parser.parse_args()
	if not opts.rhost:
		parser.error("invalid rhost")
	parts = opts.rhost.split(':')
	if len(parts) < 2:
		parser.error("invalid rhost")
	global proxy_ip, proxy_port
	try:
		proxy_port = int(parts[1])
	except:
		parser.error("invalid rhost")

	proxy_ip = parts[0]

	proxy = tornado.web.Application([('/', WsProxy)])
	proxy.listen(opts.lport)
	tornado.ioloop.IOLoop.instance().start()
