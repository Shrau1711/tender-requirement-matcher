"""A small knowledge graph, built from data the project already has, with no model calls.

graph.py is the graph itself (nodes, links that remember where they were seen, JSON and Mermaid);
standards.py links standards that are one document under several names, and standards that documents name together;
tender.py lays out a tender: items, requirement rows (shared rows once), atomic requirements and the standards they cite;
products.py links each category's product to its families and their attributes, from category.json;
layout.py puts these together for the web page (GET /runs/{id}/layout), from the tender's saved reading only.
Off by default: only with KNOWLEDGE_GRAPH=on does judging look at the standards graph (see judging/compare.py). The
layout and the product links are for showing; they never change a score.
"""
