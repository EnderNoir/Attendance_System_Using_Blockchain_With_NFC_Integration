# Configuration file for different environments

import os

class Config:
    """Base configuration"""
    DEBUG = False
    TESTING = False
    WEB3_PROVIDER = os.getenv('WEB3_PROVIDER', 'http://127.0.0.1:8545')
    CONTRACT_ADDRESS = os.getenv('CONTRACT_ADDRESS', '0x0')
    PRIVATE_KEY = os.getenv('PRIVATE_KEY', '')
    
class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    FLASK_ENV = 'development'
    
class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    FLASK_ENV = 'production'
    # Use mainnet provider in production
    WEB3_PROVIDER = os.getenv('WEB3_PROVIDER_PROD', 'https://mainnet.infura.io/v3/YOUR_INFURA_KEY')
    
class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    FLASK_ENV = 'testing'
    
# Environment selection
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
