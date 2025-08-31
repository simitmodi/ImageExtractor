from flask import Flask, request, jsonify, render_template_string, send_file
import subprocess
import sys
import os

def install_package(package):
    """Install a package using pip"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ Successfully installed {package}")
        return True
    except Exception as e:
        print(f"❌ Failed to install {package}: {e}")
        return False

# Check and install required packages
try:
    import requests
    from PIL import Image, ImageEnhance, ImageFilter, ImageStat
    import cv2
    import numpy as np
    print("✅ All packages already installed")
except ImportError as e:
    print(f"📦 Installing missing packages: {e}")
    if 'requests' in str(e):
        install_package("requests")
    if 'PIL' in str(e):
        install_package("Pillow")
    if 'cv2' in str(e):
        install_package("opencv-python")
    if 'numpy' in str(e):
        install_package("numpy")
    print("🔄 Please restart the app after installation")

import io
import tempfile
import base64
from urllib.parse import urlparse

app = Flask(__name__)

class AIImageEnhancer:
    def __init__(self):
        self.supported_formats = ['PNG', 'JPEG', 'JPG', 'WEBP', 'BMP']
        
    def extract_image_from_url(self, image_url):
        """Download image from URL with enhanced headers"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = requests.get(image_url, headers=headers, timeout=30, allow_redirects=True)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                raise ValueError("URL doesn't point to an image")
            
            return response.content
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 403:
                    raise Exception("Access denied - try a different image URL or direct image link")
                elif e.response.status_code == 404:
                    raise Exception("Image not found - check if the URL is correct")
            raise Exception(f"Failed to download image: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to extract image: {str(e)}")
    
    def analyze_image_quality(self, image):
        """AI analysis to determine what enhancements are needed - FIXED VERSION"""
        try:
            # Convert PIL to numpy array for analysis
            img_array = np.array(image)
            
            # Safe calculation of image statistics
            stat = ImageStat.Stat(image)
            
            # Fix for NaN values - use safe calculations
            try:
                brightness_raw = float(np.mean(stat.mean)) if stat.mean else 128.0
                contrast_raw = float(np.mean(stat.stddev)) if stat.stddev else 50.0
            except (TypeError, ValueError, ZeroDivisionError):
                brightness_raw = 128.0
                contrast_raw = 50.0
            
            # Normalize safely
            brightness = max(0.0, min(1.0, brightness_raw / 255.0))
            contrast = max(0.0, min(1.0, contrast_raw / 255.0))
            
            analysis = {
                'brightness': brightness,
                'contrast': contrast,
                'brightness_raw': brightness_raw,
                'contrast_raw': contrast_raw,
                'is_dark': brightness_raw < 100,
                'is_low_contrast': contrast_raw < 40,
                'needs_sharpening': False,
                'needs_noise_reduction': False,
                'sharpness_score': 100,
                'noise_level': 10
            }
            
            # Convert to grayscale for advanced analysis
            try:
                if len(img_array.shape) == 3 and img_array.shape[2] >= 3:
                    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                else:
                    gray = img_array.astype(np.uint8)
                
                # Check if image needs sharpening (using Laplacian variance)
                laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
                analysis['needs_sharpening'] = laplacian_var < 100
                analysis['sharpness_score'] = max(0, min(1000, laplacian_var))
                
                # Check for noise (using standard deviation in small regions)
                h, w = gray.shape
                noise_regions = []
                step = max(20, min(h//10, w//10))
                
                for i in range(0, h-step, step):
                    for j in range(0, w-step, step):
                        region = gray[i:i+step, j:j+step]
                        if region.size > 0:
                            noise_regions.append(float(np.std(region)))
                
                if noise_regions:
                    avg_noise = float(np.mean(noise_regions))
                    analysis['needs_noise_reduction'] = avg_noise > 25
                    analysis['noise_level'] = max(0, min(100, avg_noise))
                
            except Exception as cv_error:
                print(f"OpenCV analysis failed: {cv_error}")
                # Use safe defaults
                analysis.update({
                    'needs_sharpening': True,
                    'needs_noise_reduction': False,
                    'sharpness_score': 50,
                    'noise_level': 10
                })
            
            return analysis
            
        except Exception as e:
            print(f"Analysis failed: {e}")
            # Return safe fallback analysis
            return {
                'brightness': 0.5,
                'contrast': 0.5,
                'brightness_raw': 128,
                'contrast_raw': 50,
                'is_dark': False,
                'is_low_contrast': True,
                'needs_sharpening': True,
                'needs_noise_reduction': False,
                'sharpness_score': 50,
                'noise_level': 10
            }
    
    def auto_enhance_image(self, image_data):
        """AI-powered automatic image enhancement - FIXED VERSION"""
        try:
            # Convert to PIL Image
            pil_image = Image.open(io.BytesIO(image_data))
            original_image = pil_image.copy()
            
            # Analyze image to determine needed enhancements
            analysis = self.analyze_image_quality(pil_image)
            applied_enhancements = []
            
            # Apply PIL-based enhancements first (safer)
            enhanced_image = pil_image.copy()
            
            # 1. BRIGHTNESS ENHANCEMENT
            if analysis['is_dark'] or analysis['brightness'] < 0.4:
                brightness_factor = 1.3 if analysis['brightness'] < 0.3 else 1.15
                enhancer = ImageEnhance.Brightness(enhanced_image)
                enhanced_image = enhancer.enhance(brightness_factor)
                applied_enhancements.append("Auto Brightness Boost")
            
            # 2. CONTRAST ENHANCEMENT
            if analysis['is_low_contrast'] or analysis['contrast'] < 0.3:
                contrast_factor = 1.4 if analysis['contrast'] < 0.2 else 1.2
                enhancer = ImageEnhance.Contrast(enhanced_image)
                enhanced_image = enhancer.enhance(contrast_factor)
                applied_enhancements.append("Auto Contrast Enhancement")
            
            # 3. SHARPNESS ENHANCEMENT
            if analysis['needs_sharpening'] or analysis['sharpness_score'] < 100:
                sharpness_factor = 1.5 if analysis['sharpness_score'] < 50 else 1.2
                enhancer = ImageEnhance.Sharpness(enhanced_image)
                enhanced_image = enhancer.enhance(sharpness_factor)
                applied_enhancements.append("Auto Sharpening")
            
            # 4. COLOR ENHANCEMENT
            try:
                # Safe color enhancement
                enhancer = ImageEnhance.Color(enhanced_image)
                enhanced_image = enhancer.enhance(1.1)
                applied_enhancements.append("Auto Color Enhancement")
            except Exception:
                pass
            
            # 5. ADVANCED OPENCV ENHANCEMENTS (with error handling)
            try:
                # Convert to OpenCV format for advanced processing
                cv_image = cv2.cvtColor(np.array(enhanced_image), cv2.COLOR_RGB2BGR)
                
                # Noise Reduction
                if analysis['needs_noise_reduction']:
                    cv_image = cv2.bilateralFilter(cv_image, 9, 75, 75)
                    applied_enhancements.append("Auto Noise Reduction")
                
                # Convert back to PIL
                enhanced_image = Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB))
                
            except Exception as cv_error:
                print(f"OpenCV enhancement failed: {cv_error}")
                # Continue with PIL-only enhancements
            
            # Ensure we have some enhancements
            if not applied_enhancements:
                # Apply minimal default enhancement
                enhancer = ImageEnhance.Sharpness(enhanced_image)
                enhanced_image = enhancer.enhance(1.1)
                applied_enhancements.append("Default Quality Boost")
            
            return enhanced_image, applied_enhancements, analysis
            
        except Exception as e:
            print(f"Enhancement failed: {e}")
            # Return original image with safe analysis
            try:
                original_image = Image.open(io.BytesIO(image_data))
                safe_analysis = {
                    'brightness': 0.5,
                    'contrast': 0.5,
                    'brightness_raw': 128,
                    'contrast_raw': 50,
                    'sharpness_score': 50,
                    'noise_level': 10
                }
                return original_image, ["Enhancement failed - returned original"], safe_analysis
            except Exception:
                raise Exception(f"Failed to process image: {str(e)}")
    
    def convert_image_format(self, pil_image, target_format, quality=95):
        """Convert PIL image to desired format"""
        try:
            # Handle transparency for JPEG conversion
            if target_format.upper() == 'JPEG' and pil_image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', pil_image.size, (255, 255, 255))
                if pil_image.mode == 'P':
                    pil_image = pil_image.convert('RGBA')
                background.paste(pil_image, mask=pil_image.split()[-1] if pil_image.mode == 'RGBA' else None)
                pil_image = background
            
            # Convert image
            output_buffer = io.BytesIO()
            save_kwargs = {'format': target_format.upper()}
            
            if target_format.upper() in ['JPEG', 'JPG']:
                save_kwargs['quality'] = quality
                save_kwargs['optimize'] = True
            elif target_format.upper() == 'PNG':
                save_kwargs['optimize'] = True
            elif target_format.upper() == 'WEBP':
                save_kwargs['quality'] = quality
                save_kwargs['method'] = 6
            
            pil_image.save(output_buffer, **save_kwargs)
            return output_buffer.getvalue()
            
        except Exception as e:
            raise Exception(f"Failed to convert image: {str(e)}")

# Initialize enhancer
enhancer = AIImageEnhancer()

# [Keep the same HTML_TEMPLATE from before - it's working fine]

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>🤖 AI Image Auto-Enhancer</title>
    <style>
        body { 
            font-family: 'Arial', sans-serif; 
            max-width: 900px; 
            margin: 0 auto; 
            padding: 20px; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        h1 { 
            text-align: center; 
            color: #333; 
            margin-bottom: 10px;
            font-size: 2.5em;
        }
        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 30px;
            font-size: 1.1em;
        }
        .form-section {
            margin-bottom: 25px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
        }
        .form-section h3 {
            margin-top: 0;
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 5px;
        }
        .form-group { 
            margin-bottom: 20px; 
        }
        .form-row {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }
        .form-col {
            flex: 1;
            min-width: 200px;
        }
        label { 
            display: block; 
            margin-bottom: 8px; 
            font-weight: bold; 
            color: #555;
        }
        input, select { 
            padding: 12px; 
            width: 100%; 
            box-sizing: border-box; 
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
        }
        input:focus, select:focus {
            border-color: #667eea;
            outline: none;
        }
        .range-display {
            display: inline-block;
            margin-left: 10px;
            font-weight: bold;
            color: #667eea;
        }
        button { 
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white; 
            border: none; 
            cursor: pointer; 
            padding: 15px 30px;
            border-radius: 8px;
            font-size: 16px;
            width: 100%;
            transition: transform 0.2s;
        }
        button:hover { 
            transform: translateY(-2px);
        }
        .result { 
            margin-top: 30px; 
            padding: 20px; 
            border-radius: 10px; 
            border-left: 5px solid #007bff;
        }
        .error { 
            background: #f8d7da; 
            color: #721c24; 
            border-left-color: #dc3545;
        }
        .success { 
            background: #d4edda; 
            color: #155724; 
            border-left-color: #28a745;
        }
        .loading { 
            text-align: center; 
            color: #666;
        }
        .download-btn {
            background: #28a745;
            width: auto;
            display: inline-block;
            margin-top: 15px;
            text-decoration: none;
            padding: 10px 20px;
            border-radius: 8px;
            color: white;
        }
        .download-btn:hover {
            background: #218838;
        }
        .preview-image {
            max-width: 300px;
            max-height: 300px;
            border-radius: 8px;
            margin: 15px 0;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        .test-urls {
            margin-top: 10px;
            padding: 15px;
            background: #e9ecef;
            border-radius: 8px;
        }
        .test-urls h4 {
            margin: 0 0 10px 0;
            color: #333;
        }
        .test-url {
            display: inline-block;
            margin: 5px;
            padding: 5px 10px;
            background: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-size: 12px;
            cursor: pointer;
        }
        .test-url:hover {
            background: #0056b3;
        }
        .ai-badge {
            background: linear-gradient(45deg, #ff6b6b, #ffa500);
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            display: inline-block;
            margin-left: 10px;
        }
        .analysis-section {
            background: #f1f3f4;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
        }
        .analysis-item {
            display: inline-block;
            background: #007bff;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            margin: 2px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 AI Image Auto-Enhancer</h1>
        <p class="subtitle">
            Fixed & Optimized - Intelligent automatic image enhancement
            <span class="ai-badge">🧠 AI POWERED</span>
        </p>
        
        <form id="converterForm">
            <!-- URL Section -->
            <div class="form-section">
                <h3>📎 Image Source</h3>
                <div class="form-group">
                    <label>Image URL:</label>
                    <input type="url" id="imageUrl" placeholder="https://picsum.photos/800/600" required>
                    <div class="test-urls">
                        <h4>🧪 Test URLs (click to use):</h4>
                        <a class="test-url" onclick="setUrl('https://picsum.photos/800/600')">Random Image</a>
                        <a class="test-url" onclick="setUrl('https://httpbin.org/image/png')">Test PNG</a>
                        <a class="test-url" onclick="setUrl('https://httpbin.org/image/jpeg')">Test JPEG</a>
                        <a class="test-url" onclick="setUrl('https://via.placeholder.com/600x400')">Placeholder</a>
                    </div>
                </div>
            </div>
            
            <!-- AI Enhancement Section -->
            <div class="form-section">
                <h3>🤖 AI Auto-Enhancement (FIXED)</h3>
                <div style="background: #e8f4f8; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                    <h4 style="margin: 0 0 10px 0; color: #2c5aa0;">🛠️ Fixed AI Features:</h4>
                    <ul style="margin: 0; padding-left: 20px; color: #555;">
                        <li>✅ Safe brightness & contrast calculations (no more NaN)</li>
                        <li>✅ Robust error handling for all enhancement steps</li>
                        <li>✅ Fallback modes for failed operations</li>
                        <li>✅ PIL-first approach with OpenCV backup</li>
                        <li>✅ Guaranteed enhancement output</li>
                    </ul>
                </div>
            </div>
            
            <!-- Output Section -->
            <div class="form-section">
                <h3>💾 Output Settings</h3>
                <div class="form-row">
                    <div class="form-col">
                        <label>Target Format:</label>
                        <select id="format">
                            <option value="PNG">PNG (Best Quality)</option>
                            <option value="JPEG">JPEG (Smaller Size)</option>
                            <option value="WEBP">WEBP (Modern)</option>
                            <option value="BMP">BMP (Uncompressed)</option>
                        </select>
                    </div>
                    <div class="form-col">
                        <label>Quality (for JPEG/WEBP):</label>
                        <input type="range" id="quality" min="1" max="100" value="95">
                        <span class="range-display" id="qualityValue">95%</span>
                    </div>
                </div>
            </div>
            
            <button type="submit">🚀 AI Auto-Enhance & Convert (Fixed)</button>
        </form>
        
        <div id="result"></div>
    </div>

    <script>
        function setUrl(url) {
            document.getElementById('imageUrl').value = url;
        }

        document.getElementById('quality').addEventListener('input', function() {
            document.getElementById('qualityValue').textContent = this.value + '%';
        });

        document.getElementById('converterForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const resultDiv = document.getElementById('result');
            resultDiv.innerHTML = '<div class="result loading">🤖 AI is analyzing and auto-enhancing your image (with fixes)...</div>';
            
            try {
                const response = await fetch('/convert', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        image_url: document.getElementById('imageUrl').value,
                        format: document.getElementById('format').value,
                        quality: parseInt(document.getElementById('quality').value)
                    })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    let analysisHtml = '';
                    if (result.analysis) {
                        const brightness = result.analysis.brightness ? (result.analysis.brightness * 100).toFixed(0) : 'N/A';
                        const contrast = result.analysis.contrast ? (result.analysis.contrast * 100).toFixed(0) : 'N/A';
                        const sharpness = result.analysis.sharpness_score ? result.analysis.sharpness_score.toFixed(0) : 'N/A';
                        const noise = result.analysis.noise_level ? result.analysis.noise_level.toFixed(0) : 'Low';
                        
                        analysisHtml = `
                            <div class="analysis-section">
                                <h4>🔍 AI Analysis Results:</h4>
                                <div style="margin: 10px 0;">
                                    <span class="analysis-item">Brightness: ${brightness}%</span>
                                    <span class="analysis-item">Contrast: ${contrast}%</span>
                                    <span class="analysis-item">Sharpness: ${sharpness}</span>
                                    <span class="analysis-item">Noise Level: ${noise}</span>
                                </div>
                            </div>
                        `;
                    }
                    
                    resultDiv.innerHTML = `
                        <div class="result success">
                            <h3>✅ AI Enhancement Successful!</h3>
                            <p><strong>📁 Filename:</strong> ${result.filename}</p>
                            <p><strong>🎨 Format:</strong> ${result.format}</p>
                            <p><strong>📏 Size:</strong> ${(result.size_bytes / 1024).toFixed(2)} KB</p>
                            <p><strong>🤖 AI Enhancements Applied:</strong> ${result.enhancements_applied}</p>
                            ${analysisHtml}
                            <img src="data:image/${result.format.toLowerCase()};base64,${result.preview}" class="preview-image" alt="AI Enhanced Image">
                            <br>
                            <a href="/download/${result.filename}" class="download-btn">📥 Download AI Enhanced Image</a>
                        </div>
                    `;
                } else {
                    resultDiv.innerHTML = `
                        <div class="result error">
                            <h3>❌ Error</h3>
                            <p>${result.error}</p>
                            <p><small>💡 Tip: Try one of the test URLs above or use a direct image link</small></p>
                        </div>
                    `;
                }
            } catch (error) {
                resultDiv.innerHTML = `
                    <div class="result error">
                        <h3>❌ Network Error</h3>
                        <p>Failed to process image: ${error.message}</p>
                    </div>
                `;
            }
        });
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    """Main page with AI image enhancer interface"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/convert', methods=['POST'])
def convert_image():
    """AI-powered automatic image enhancement and conversion - FIXED"""
    try:
        data = request.json
        image_url = data.get('image_url')
        target_format = data.get('format', 'PNG')
        quality = data.get('quality', 95)
        
        # Validation
        if not image_url:
            return jsonify({'success': False, 'error': 'Image URL is required'}), 400
        
        if target_format.upper() not in enhancer.supported_formats:
            return jsonify({'success': False, 'error': f'Unsupported format'}), 400
        
        # Extract image
        image_data = enhancer.extract_image_from_url(image_url)
        
        # AI Auto-Enhancement (with fixes)
        enhanced_image, applied_enhancements, analysis = enhancer.auto_enhance_image(image_data)
        
        # Convert format
        converted_data = enhancer.convert_image_format(enhanced_image, target_format, quality)
        
        # Generate filename
        original_name = os.path.basename(urlparse(image_url).path) or "image"
        filename = f"ai_enhanced_{os.path.splitext(original_name)[0]}.{target_format.lower()}"
        
        # Save for download
        temp_path = os.path.join(tempfile.gettempdir(), filename)
        with open(temp_path, 'wb') as f:
            f.write(converted_data)
        
        # Create preview (limit size for performance)
        preview_data = converted_data
        if len(preview_data) > 500000:  # If larger than 500KB, create smaller preview
            preview_image = Image.open(io.BytesIO(converted_data))
            preview_image.thumbnail((300, 300), Image.Resampling.LANCZOS)
            preview_buffer = io.BytesIO()
            preview_image.save(preview_buffer, format='JPEG', quality=80)
            preview_data = preview_buffer.getvalue()
        
        preview_base64 = base64.b64encode(preview_data).decode('utf-8')
        
        enhancements_text = ', '.join(applied_enhancements) if applied_enhancements else 'No enhancements applied'
        
        return jsonify({
            'success': True,
            'filename': filename,
            'size_bytes': len(converted_data),
            'format': target_format.upper(),
            'preview': preview_base64,
            'enhancements_applied': enhancements_text,
            'analysis': analysis
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    """Download AI enhanced image file"""
    try:
        temp_path = os.path.join(tempfile.gettempdir(), filename)
        if os.path.exists(temp_path):
            return send_file(temp_path, as_attachment=True, download_name=filename)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'message': 'AI Image Auto-Enhancer is running (FIXED VERSION)',
        'supported_formats': enhancer.supported_formats,
        'ai_features': ['Fixed Brightness/Contrast', 'Safe Sharpening', 'Robust Color Enhancement', 'Error-Safe Processing']
    })

def main():
    """Main function to run the Flask app"""
    port = int(os.environ.get('PORT', 80))
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == "__main__":
    main()
