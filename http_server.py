import http.server
import socketserver
import threading
import os

class HTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """
    HTTP请求处理器，提供静态文件服务
    """
    def __init__(self, *args, **kwargs):
        # 设置静态文件目录
        web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')
        super().__init__(*args, directory=web_dir, **kwargs)

class HTTPServer:
    """
    HTTP服务器：提供H5页面
    """
    
    def __init__(self):
        self.server = None
        self.server_thread = None
        self.is_running = False
    
    def start(self, host="0.0.0.0", port=8765):
        """
        启动HTTP服务器
        
        Args:
            host: 主机地址
            port: 端口
        """
        try:
            # 创建服务器
            self.server = socketserver.TCPServer((host, port), HTTPRequestHandler)
            self.is_running = True
            
            # 在单独的线程中运行服务器
            self.server_thread = threading.Thread(
                target=self.server.serve_forever,
                daemon=True
            )
            self.server_thread.start()
            
            print(f"🌐 HTTP 服务器已启动，监听 {host}:{port}")
            print(f"📁 静态文件目录: {os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')}")
            print(f"🌍 访问地址: http://{host}:{port}")
            
        except Exception as e:
            print(f"HTTP 服务器启动失败: {e}")
            self.is_running = False
    
    def stop(self):
        """
        停止HTTP服务器
        """
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        
        if self.server_thread:
            self.server_thread.join(timeout=5)
            self.server_thread = None
        
        self.is_running = False
        print("🛑 HTTP 服务器已停止")
    
    def is_service_running(self) -> bool:
        """
        检查服务是否运行
        
        Returns:
            bool: 服务是否运行
        """
        return self.is_running