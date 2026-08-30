from flask import Flask
app = Flask(__name__)
@app.route("/")
def accueil():
        return "Hello World !"
@app.route("/taches")
def taches():
     return "Liste des taches (bientot)"
if __name__ == "__main__":
    app.run(debug=True)