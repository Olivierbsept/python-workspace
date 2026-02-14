
"""
Spyder Editor

This is a temporary script file.
"""

import xml.etree.ElementTree as ET
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLineEdit, QLabel, QTextEdit, QComboBox
import os

class Fenetre(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dico")
        self.layout_main=QVBoxLayout()

        self.label_type = QLabel("Sélectionnez un type :", self)

        self.combobox_type = QComboBox(self)
        self.combobox_type.addItems(types_list)
        self.combobox_type.currentTextChanged.connect(self.update_label)
        
        self.bouton_ajouter=QPushButton("Valider l'ajout")
        self.bouton_ajouter.clicked.connect(self.stocker)
        
        self.label_ajouter=QLabel("Ajouter un mot")
        self.layout_ajouter=QVBoxLayout()
        self.input_field_ajouter = QLineEdit()
        self.layout_ajouter.addWidget(self.label_ajouter)
        self.layout_ajouter.addWidget(self.input_field_ajouter)
        self.layout_ajouter.addWidget(self.label_type)
        self.layout_ajouter.addWidget(self.combobox_type)
        self.layout_ajouter.addWidget(self.bouton_ajouter)

        self.label_supprimer=QLabel("Supprimer un mot")
        self.layout_supprimer=QVBoxLayout()
        self.input_field_supprimer = QLineEdit()
        self.bouton_supprimer=QPushButton("Valider la suppression")
        self.bouton_supprimer.clicked.connect(self.supprimer)
        self.layout_supprimer.addWidget(self.label_supprimer)
        self.layout_supprimer.addWidget(self.input_field_supprimer)
        self.layout_supprimer.addWidget(self.bouton_supprimer)

        self.layout_classer=QVBoxLayout()
        self.bouton_classer=QPushButton("Classer")
        self.bouton_classer.clicked.connect(self.classer)
        self.layout_classer.addWidget(self.bouton_classer)

        self.layout_chercher= QVBoxLayout()
        self.text_area_chercher = QTextEdit(self)
        self.text_area_chercher.setPlaceholderText("Entrez votre texte ici...")

        # Ajouter les sections au layout principal
        self.layout_main.addLayout(self.layout_ajouter)     
        self.layout_main.addLayout(self.layout_supprimer)
        self.layout_main.addLayout(self.layout_classer)
        self.layout_main.addWidget(self.text_area_chercher)
        self.setLayout(self.layout_main)
        
        self.log_area = QTextEdit(self)
        self.log_area.setReadOnly(True)  # Empêche la modification manuelle
        # Disposition verticale
        self.layout_main.addWidget(self.log_area)
        self.resize(500, 400)
        self.suffixes_list = []  # Stocker temporairement les suffixes

    
    def update_label(self, text):
        """Met à jour le label avec la sélection."""
        self.label_type.setText(f"Type sélectionné : {text}")
        # Trouver le nœud correspondant au type sélectionné
        type_node = root.find(f".//types/{text}")  # Ex: .//types/RxSignal
    
        # Récupérer les suffixes (balises enfants du type)
        self.suffixes_list = [suffix.text for suffix in type_node if suffix.text] if type_node is not None else []
        #print (suffixes_list)
    
    def stocker(self):     
        for suffix in self.suffixes_list:
            nouveaumot=self.input_field_ajouter.text()+suffix
            with open (chemin,"r",encoding="utf-8") as fichier:
                mots=fichier.readlines()
                trouve=False
                for num, mot in enumerate(mots,start=1):
                    if nouveaumot == mot.strip():
                        trouve=True
                        self.log_area.append("Le mot : '"+nouveaumot+"' n'est pas ajouté car déjà présent.")
                        break
                if not trouve:
                    with open (chemin,"a",encoding="utf-8") as fichier:
                        fichier.write(nouveaumot+"\n")
                        self.log_area.append("Le mot :'"+nouveaumot+"' été ajouté.")

    def supprimer(self):
        nouveaumot=self.input_field_supprimer.text()
        with open (chemin,"r",encoding="utf-8") as fichier:
            mots=fichier.readlines()
            index = next((i for i, mot in enumerate(mots)if nouveaumot == mot.strip()),None)
            if index is None:
                self.log_area.append("Le mot :'"+nouveaumot+"' n'a pas été supprimé car absent.")
                return
            with open(chemin,'w',encoding='utf-8') as fichier1:
                fichier1.writelines(mots[:index])
                fichier1.writelines(mots[index+1:])
            self.log_area.append("Le mot : '"+nouveaumot+"' a été supprimé.")
                  
    def classer(self):
        with open (chemin,"r",encoding="utf-8") as fichier:
            mots=fichier.readlines()
            mots_classes=sorted(set(mots))
            with open(chemin,'w',encoding='utf-8') as fichier1:
                fichier1.writelines(mots_classes)
            self.log_area.append("Les mots ont été classés.")

root_path = os.path.abspath(os.sep)
cheminXml = os.path.abspath("/Users/olivierbessettemac/python-workspace/Dico.xml")
tree = ET.parse(cheminXml)
root=tree.getroot()
# Trouver la balise <path> sous <filePath>
contenu = root.find("filePath/path")
if contenu is not None and contenu.text:  # Vérifie si la balise <path> existe et contient du texte
    chemin = os.path.abspath(contenu.text.strip())  # Nettoie et convertit en chemin absolu

    # Vérifie si le fichier référencé par le XML existe avant de l'ouvrir
    if os.path.exists(chemin):
        with open(chemin, "r", encoding="utf-8") as fichier:
            mots = fichier.readlines()
            print(mots)
        # Récupérer les types sous <types>
        types_node = root.find("types")
        types_list = [type_elem.tag for type_elem in types_node] if types_node is not None else []

    else:
        print(f"Erreur : le fichier '{chemin}' n'existe pas.")
else:
    print("Erreur : balise <path> introuvable ou vide dans le fichier XML.")
     
app = QApplication([])
fenetre = Fenetre()
fenetre.show()
app.exec_()

print("fin")

#cheminfichier = os.path.join(,"dico.txt")


