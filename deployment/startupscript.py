#!/usr/bin/env python3
"""
MCP Server Startup Script - Start all servers in the correct order
"""

import subprocess
import time
import requests
import sys
import os
from concurrent.futures import ThreadPoolExecutor
import signal

class MCPServerManager:
    """Manages startup and health checking of all MCP servers"""
    
    def __init__(self):
        self.servers = {
            "servicenow": {
                "script": "servicenow_mcp_server.py",
                "port": 8082,
                "health_url": "http://localhost:8082/health",
                "process": None
            },
            "database": {
                "script": "database_mcp_server.py", 
                "port": 8083,
                "health_url": "http://localhost:8083/health",
                "process": None
            },
            "research": {
                "script": "research_mcp_server.py",
                "port": 8084,
                "health_url": "http://localhost:8084/health",
                "process": None
            }
        }
        self.running_processes = []
    
    def check_port_available(self, port: int) -> bool:
        """Check if a port is available"""
        try:
            response = requests.get(f"http://localhost:{port}/health", timeout=2)
            return False  # Port is occupied
        except requests.exceptions.RequestException:
            return True  # Port is available
    
    def start_server(self, server_name: str, server_config: dict) -> bool:
        """Start a single MCP server"""
        script_name = server_config["script"]
        port = server_config["port"]
        
        print(f"🚀 Starting {server_name} server on port {port}...")
        
        # Check if script exists
        if not os.path.exists(script_name):
            print(f"❌ Script {script_name} not found!")
            return False
        
        # Check if port is available
        if not self.check_port_available(port):
            print(f"⚠️ Port {port} already in use, attempting to use existing service...")
            return self.health_check(server_name, server_config)
        
        try:
            # Start the server process
            process = subprocess.Popen([
                sys.executable, script_name,
                "--host", "localhost",
                "--port", str(port)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            server_config["process"] = process
            self.running_processes.append(process)
            
            # Wait a moment for startup
            time.sleep(3)
            
            # Health check
            if self.health_check(server_name, server_config):
                print(f"✅ {server_name} server started successfully")
                return True
            else:
                print(f"❌ {server_name} server failed health check")
                return False
                
        except Exception as e:
            print(f"❌ Failed to start {server_name} server: {e}")
            return False
    
    def health_check(self, server_name: str, server_config: dict) -> bool:
        """Perform health check on a server"""
        health_url = server_config["health_url"]
        
        for attempt in range(5):  # 5 attempts with delays
            try:
                response = requests.get(health_url, timeout=5)
                if response.status_code == 200:
                    return True
            except requests.exceptions.RequestException:
                pass
            
            time.sleep(2)  # Wait 2 seconds between attempts
        
        return False
    
    def start_all_servers(self):
        """Start all MCP servers"""
        print("🔧 Starting MCP Server Manager...")
        print("=" * 50)
        
        success_count = 0
        
        # Start servers sequentially to avoid conflicts
        for server_name, server_config in self.servers.items():
            if self.start_server(server_name, server_config):
                success_count += 1
            else:
                print(f"⚠️ Continuing without {server_name} server...")
        
        print("=" * 50)
        print(f"📊 Startup Summary: {success_count}/{len(self.servers)} servers running")
        
        if success_count > 0:
            print("\n🌐 Server URLs:")
            for server_name, config in self.servers.items():
                if self.health_check(server_name, config):
                    print(f"   • {server_name.title()}: http://localhost:{config['port']}")
                    print(f"     - Health: {config['health_url']}")
                    print(f"     - SSE: http://localhost:{config['port']}/sse")
        
        return success_count > 0
    
    def stop_all_servers(self):
        """Stop all running servers"""
        print("\n🛑 Stopping all MCP servers...")
        
        for process in self.running_processes:
            try:
                process.terminate()
                process.wait(timeout=5)
                print("✅ Server stopped gracefully")
            except subprocess.TimeoutExpired:
                process.kill()
                print("⚠️ Server force-killed")
            except Exception as e:
                print(f"❌ Error stopping server: {e}")
    
    def monitor_servers(self):
        """Monitor server health and restart if needed"""
        print("\n👁️ Monitoring servers (Ctrl+C to stop)...")
        
        try:
            while True:
                print("\n📡 Health Check:", end="")
                all_healthy = True
                
                for server_name, config in self.servers.items():
                    if self.health_check(server_name, config):
                        print(f" {server_name}:✅", end="")
                    else:
                        print(f" {server_name}:❌", end="")
                        all_healthy = False
                
                if all_healthy:
                    print(" - All systems operational")
                else:
                    print(" - Some servers down")
                
                time.sleep(10)  # Check every 10 seconds
                
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n🛑 Shutting down MCP servers...")
    sys.exit(0)

def main():
    """Main function"""
    signal.signal(signal.SIGINT, signal_handler)
    
    manager = MCPServerManager()
    
    try:
        # Start all servers
        if manager.start_all_servers():
            print("\n🎉 MCP infrastructure ready!")
            print("\n📋 Next steps:")
            print("   1. Open a new terminal")
            print("   2. Run: streamlit run fixed_streamlit_app.py")
            print("   3. Test the chatbot interface")
            
            # Monitor servers
            manager.monitor_servers()
        else:
            print("\n❌ Failed to start MCP infrastructure")
            
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    finally:
        manager.stop_all_servers()

if __name__ == "__main__":
    print("🚀 MCP Server Manager v1.0")
    print("Manages ServiceNow, Database, and Research MCP servers")
    print("=" * 60)
    
    main()