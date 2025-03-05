from flask import Flask

app = Flask(__name__)

@app.route('/')
def index():
    return "Hello, World! The test server is running."

@app.route('/test')
def test():
    return "Test endpoint is working!"

if __name__ == "__main__":
    print("Starting test server on 0.0.0.0:8000")
    app.run(host='0.0.0.0', port=8000, debug=True) 