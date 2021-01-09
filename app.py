from flask import Flask
import os

app = Flask(__name__)

@app.route(f"/", methods=['GET', 'POST'])
def hello():
    return "Hello World"



if __name__ == "__main__":
    app.run(threaded=True)
