#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Apr 21 09:38:06 2025

@author: olivierbessettemac
"""

class Node:
    def __init__(self, name, identity, horameter):
        self.name = name
        self.identity = identity
        self.horameter = horameter

    def __repr__(self):
        return f"{self.name} -> ID: {self.identity}, H: {self.horameter}"
    
    def update_state(self, others):
        all_nodes = [self] + others
        ids = [n.identity for n in all_nodes]
        hrs = [n.horameter for n in all_nodes]
        
        id_self, id_1, id_2 = ids
        hr_self, hr_1, hr_2 = hrs
        
        # Cas 1: Tous identiques
        if id_self == id_1 == id_2:
            self.horameter = max(hrs)
        
        # Cas 2: i.id != j.id == k.id
        elif id_self != id_1 == id_2:
            self.identity = id_1
            self.horameter = max(hr_1, hr_2)
        
        # Cas 3: i.id == j.id != k.id OU tous différents -> rien ne change
        # Donc on ne fait rien ici


# --- Initialisation des 3 nœuds ---
nodeA = Node("A", "id1", 5)
nodeB = Node("B", "id2", 7)
nodeC = Node("C", "id3", 10)

nodes = [nodeA, nodeB, nodeC]

print("ÉTAT INITIAL :")
for n in nodes:
    print(n)

# --- Mise à jour de l'état de chaque nœud ---
for i in range(3):
    others = [nodes[j] for j in range(3) if j != i]
    nodes[i].update_state(others)

print("\nÉTAT APRÈS SYNC :")
for n in nodes:
    print(n)