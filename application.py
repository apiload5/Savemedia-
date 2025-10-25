from flask import Flask, request, jsonify, redirect, url_for
from flask_cors import CORS  # CORS ko wapis import kiya
import os
import requests
import yt_dlp
from PIL import Image
import io
import base64
import logging
import time
import gc
import re
from functools import wraps
from urllib.parse import urlparse
import json

# ======================================================================
# 1. AWS/DigitalOcean compatible initialization
# ======================================================================

application = Flask(__name__)

# ONLY allow traffic from your specific frontend domain
# Ye configuration sirf savemedia.online ko requests bhejne ki ijazat degi
CORS(
    application, 
    origins="https://savemedia.online",  # SIRF is domain ko allow karo
    methods=["GET", "POST", "OPTIONS"], 
    supports_credentials=True
)

# Configure logging for CloudWatch or Droplet System Logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

# Rate limiting storage
request_counts = {}

# ======================================================================
# 2. Helper Functions (Waisi hi Rahengi)
# ======================================================================

def rate_limit(max_requests=10, window=60):
    """Rate limiting decorator"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.remote_addr or 'unknown'
            current_time = time.time()
            
            if client_ip not in request_counts:
                request_counts[client_ip] = []
            
            # Clean old requests
            request_counts[client_ip] = [
                req_time for req_time in request_counts[client_ip]
                if current_time - req_time < window
            ]
            
            if len(request_counts[client_ip]) >= max_requests:
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                return jsonify({"error": "Rate limit exceeded. Try again later."}), 429
            
            request_counts[client_ip].append(current_time)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def cleanup_memory():
    """Force garbage collection"""
    gc.collect()

def is_valid_url(url):
    """Validate URL format"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def detect_platform(url):
    """Detect social media platform from URL"""
    url = url.lower()
    
    if 'youtube.com' in url or 'youtu.be' in url:
        return 'youtube'
    # ... (baaki platforms ki detection waise hi rahegi) ...
    elif 'instagram.com' in url:
        return 'instagram'
    elif 'facebook.com' in url or 'fb.watch' in url:
        return 'facebook'
    elif 'twitter.com' in url or 'x.com' in url:
        return 'twitter'
    elif 'tiktok.com' in url:
        return 'tiktok'
    elif 'linkedin.com' in url:
        return 'linkedin'
    elif 'pinterest.com' in url:
        return 'pinterest'
    elif 'reddit.com' in url:
        return 'reddit'
    elif 'vimeo.com' in url:
        return 'vimeo'
    elif 'dailymotion.com' in url:
        return 'dailymotion'
    else:
        return 'generic'

# ======================================================================
# 3. Routes (UPDATED HOME ROUTE)
# ======================================================================

# Health Check Endpoint
@application.route('/health')
def health_check():
    """Health check for Load Balancer/Uptime monitoring"""
    return jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "service": "SaveMedia API"
    }), 200

# Root endpoint (AB FRONTEND NAHI, API INFO SERVE HOGA)
@application.route('/')
def home():
    """API information endpoint (No frontend serving)"""
    return jsonify({
        "message": "SaveMedia API - Multi-Platform Media Downloader",
        "version": "2.0",
        "status": "active",
        "supported_platforms": [
            "YouTube", "Instagram", "Facebook", "Twitter/X", 
            "TikTok", "LinkedIn", "Pinterest", "Reddit", 
            "Vimeo", "Dailymotion"
        ],
        "endpoints": {
            "health": "/health",
            "download": "/download",
            "info": "/info",
            "platforms": "/platforms"
        },
        "usage": {
            "method": "POST",
            "body": {"url": "media_url"},
            "rate_limit": "5 requests per minute from savemedia.online"
        }
    })

@application.route('/platforms')
def supported_platforms():
    """List all supported platforms"""
    # ... (function body waisa hi rahega) ...
    return jsonify({
        "supported_platforms": {
            "youtube": {
                "name": "YouTube",
                "formats": ["mp4", "webm", "mp3"],
                "example": "https://youtube.com/watch?v=..."
            },
            "instagram": {
                "name": "Instagram",
                "formats": ["mp4", "jpg"],
                "example": "https://instagram.com/p/..."
            },
            "facebook": {
                "name": "Facebook",
                "formats": ["mp4"],
                "example": "https://facebook.com/watch?v=..."
            },
            "twitter": {
                "name": "Twitter/X",
                "formats": ["mp4", "jpg"],
                "example": "https://twitter.com/user/status/..."
            },
            "tiktok": {
                "name": "TikTok",
                "formats": ["mp4"],
                "example": "https://tiktok.com/@user/video/..."
            },
            "vimeo": {
                "name": "Vimeo",
                "formats": ["mp4"],
                "example": "https://vimeo.com/..."
            }
        }
    })


@application.route('/info', methods=['POST'])
@rate_limit(max_requests=15, window=60)
def get_media_info():
    """Get media information without downloading"""
    # ... (function body waisa hi rahega) ...
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({"error": "URL is required"}), 400
        
        url = data['url'].strip()
        if not is_valid_url(url):
            return jsonify({"error": "Invalid URL format"}), 400
        
        platform = detect_platform(url)
        logger.info(f"Getting info for {platform} URL: {url}")
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'socket_timeout': 30,
            'retries': 3,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            result = {
                "platform": platform,
                "title": info.get('title', 'Unknown'),
                "duration": info.get('duration'),
                "uploader": info.get('uploader', 'Unknown'),
                "view_count": info.get('view_count'),
                "upload_date": info.get('upload_date'),
                "description": info.get('description', '')[:200] + '...' if info.get('description') else '',
                "thumbnail": info.get('thumbnail'),
                "formats_available": len(info.get('formats', [])),
                "url": url
            }
            
            cleanup_memory()
            return jsonify(result)
            
    except Exception as e:
        logger.error(f"Info extraction error: {str(e)}")
        cleanup_memory()
        return jsonify({
            "error": "Failed to extract media information",
            "details": str(e)
        }), 500


@application.route('/download', methods=['POST'])
@rate_limit(max_requests=5, window=60)
def download_media():
    """Universal media downloader for all platforms"""
    # ... (function body waisa hi rahega) ...
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({"error": "URL is required"}), 400
        
        url = data['url'].strip()
        quality = data.get('quality', 'best')
        format_type = data.get('format', 'mp4')
        
        if not is_valid_url(url):
            return jsonify({"error": "Invalid URL format"}), 400
        
        platform = detect_platform(url)
        logger.info(f"Downloading from {platform}: {url}")
        
        # Platform-specific configurations
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': '/tmp/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
            'retries': 3,
            'extract_flat': False,
        }
        
        # Quality settings
        if quality == 'high':
            ydl_opts['format'] = 'best[height<=1080]/best'
        elif quality == 'medium':
            ydl_opts['format'] = 'best[height<=720]/best'
        elif quality == 'low':
            ydl_opts['format'] = 'worst[height>=360]/worst'
        
        # Audio only
        if format_type == 'mp3':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        
        # Platform-specific optimizations
        if platform == 'instagram':
            ydl_opts['format'] = 'best'
        elif platform == 'twitter':
            ydl_opts['format'] = 'best[ext=mp4]'
        elif platform == 'tiktok':
            ydl_opts['format'] = 'best[ext=mp4]/best'
        elif platform == 'facebook':
            ydl_opts['format'] = 'best[ext=mp4]/best'
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info first
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return jsonify({"error": "Could not extract media information"}), 400
            
            # Get download URL
            if 'url' in info:
                download_url = info['url']
            elif 'formats' in info and info['formats']:
                # Find best format
                formats = info['formats']
                best_format = None
                
                for fmt in formats:
                    if fmt.get('url') and fmt.get('ext') == 'mp4':
                        best_format = fmt
                        break
                
                if not best_format and formats:
                    best_format = formats[-1]
                
                download_url = best_format['url'] if best_format else None
            else:
                return jsonify({"error": "No downloadable formats found"}), 400
            
            if not download_url:
                return jsonify({"error": "Could not get download URL"}), 400
            
            result = {
                "success": True,
                "platform": platform,
                "title": info.get('title', 'Unknown'),
                "download_url": download_url,
                "duration": info.get('duration'),
                "uploader": info.get('uploader', 'Unknown'),
                "thumbnail": info.get('thumbnail'),
                "format": info.get('ext', 'mp4'),
                "quality": quality,
                "file_size": info.get('filesize') or info.get('filesize_approx'),
                "view_count": info.get('view_count'),
                "upload_date": info.get('upload_date')
            }
            
            cleanup_memory()
            logger.info(f"Successfully processed {platform} download: {info.get('title', 'Unknown')}")
            return jsonify(result)
            
    except yt_dlp.DownloadError as e:
        logger.error(f"yt-dlp download error: {str(e)}")
        cleanup_memory()
        return jsonify({
            "error": "Download failed",
            "details": "Media may be private, deleted, or not supported",
            "platform": platform if 'platform' in locals() else 'unknown'
        }), 400
        
    except Exception as e:
        logger.error(f"Unexpected download error: {str(e)}")
        cleanup_memory()
        return jsonify({
            "error": "An unexpected error occurred",
            "details": str(e)
        }), 500

# ======================================================================
# 4. Legacy Endpoints (Waisi hi Rahengi)
# ======================================================================

@application.route('/youtube', methods=['POST'])
@rate_limit(max_requests=5, window=60)
def youtube_download():
    # ... (function body waisa hi rahega) ...
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({"error": "URL is required"}), 400
        
        # Redirect to universal download endpoint
        request.json = data
        return download_media()
        
    except Exception as e:
        logger.error(f"YouTube download error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@application.route('/instagram', methods=['POST'])
@rate_limit(max_requests=5, window=60)
def instagram_download():
    # ... (function body waisa hi rahega) ...
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({"error": "URL is required"}), 400
        
        # Redirect to universal download endpoint
        request.json = data
        return download_media()
        
    except Exception as e:
        logger.error(f"Instagram download error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@application.route('/facebook', methods=['POST'])
@rate_limit(max_requests=5, window=60)
def facebook_download():
    # ... (function body waisa hi rahega) ...
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({"error": "URL is required"}), 400
        
        # Redirect to universal download endpoint
        request.json = data
        return download_media()
        
    except Exception as e:
        logger.error(f"Facebook download error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@application.route('/twitter', methods=['POST'])
@rate_limit(max_requests=5, window=60)
def twitter_download():
    # ... (function body waisa hi rahega) ...
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({"error": "URL is required"}), 400
        
        # Redirect to universal download endpoint
        request.json = data
        return download_media()
        
    except Exception as e:
        logger.error(f"Twitter download error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ======================================================================
# 5. Error Handlers and Main Block (Waisi hi Rahengi)
# ======================================================================

# Error handlers
@application.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Endpoint not found",
        "message": "Please check the API documentation at the root endpoint"
    }), 404

@application.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "error": "Method not allowed",
        "message": "Please use POST method for download endpoints"
    }), 405

@application.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        "error": "Internal server error",
        "message": "Please try again later"
    }), 500

# AWS/DigitalOcean compatible main block
if __name__ == '__main__':
    # Local development
    port = int(os.environ.get('PORT', 5000))
    application.run(debug=True, host='0.0.0.0', port=port)
else:
    # Production on DigitalOcean (Gunicorn will run this)
    application.debug = False
    logger.info("SaveMedia API started in production mode on DigitalOcean")
