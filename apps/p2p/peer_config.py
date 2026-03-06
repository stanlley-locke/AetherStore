"""
Peer Configuration Manager
Loads and manages peer configuration from JSON file
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from django.conf import settings

class PeerConfigManager:
    """Manages peer configuration from JSON file"""
    
    DEFAULT_CONFIG_PATH = 'config/peers.json'
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """Load peer configuration from JSON file"""
        # Try multiple locations
        possible_paths = [
            Path(self.config_path),
            Path(settings.BASE_DIR) / self.config_path,
            Path(__file__).parent.parent.parent / self.config_path,
        ]
        
        for path in possible_paths:
            if path.exists():
                try:
                    with open(path, 'r') as f:
                        return json.load(f)
                except Exception as e:
                    print(f"Error loading peer config from {path}: {e}")
        
        # Return default config if file not found
        return self._get_default_config()
    
    def _get_default_config(self) -> dict:
        """Default configuration if no file exists"""
        return {
            'bootstrap_node': {
                'node_id': 'bootstrap-1',
                'endpoint': 'http://localhost:8001'
            },
            'default_peers': [],
            'gossip_config': {
                'interval_seconds': 10,
                'fanout': 3,
                'node_timeout_seconds': 60,
                'max_peers': 100
            }
        }
    
    def get_bootstrap_node(self) -> Optional[dict]:
        """Get bootstrap node configuration"""
        return self.config.get('bootstrap_node')
    
    def get_default_peers(self) -> List[dict]:
        """Get list of default peers"""
        return self.config.get('default_peers', [])
    
    def get_gossip_config(self) -> dict:
        """Get gossip protocol configuration"""
        return self.config.get('gossip_config', {})
    
    def add_peer(self, node_id: str, endpoint: str):
        """Add peer to configuration"""
        if 'default_peers' not in self.config:
            self.config['default_peers'] = []
        
        # Check if peer already exists
        for peer in self.config['default_peers']:
            if peer.get('node_id') == node_id:
                peer['endpoint'] = endpoint
                return
        
        # Add new peer
        self.config['default_peers'].append({
            'node_id': node_id,
            'endpoint': endpoint
        })
        
        # Save configuration
        self._save_config()
    
    def _save_config(self):
        """Save configuration to JSON file"""
        config_path = Path(settings.BASE_DIR) / self.config_path
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump(self.config, f, indent=4)
    
    def reload(self):
        """Reload configuration from file"""
        self.config = self._load_config()


# Singleton instance
_peer_config = None

def get_peer_config() -> PeerConfigManager:
    """Get singleton peer config manager"""
    global _peer_config
    if _peer_config is None:
        _peer_config = PeerConfigManager()
    return _peer_config
