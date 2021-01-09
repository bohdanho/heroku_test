from flask import Flask
import os

app = Flask(__name__)

@app.route(f"/", methods=['GET', 'POST'])
def hello():
    return "Hello World"



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)), threaded=True)
