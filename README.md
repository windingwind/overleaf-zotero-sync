# Link Overleaf project with Zotero

## Usage

## Motivation

[Overleaf](https://www.overleaf.com/) is a popular online LaTeX editor. It has [built-in support](https://www.overleaf.com/learn/how-to/How_to_link_Zotero_to_your_Overleaf_account) for synchronizing bibliography from Zotero, however:

- It requires the subscription plan
- Only the creator of the linked file can update the citations

Other options include using the [Zotero Better BibTeX](https://retorque.re/zotero-better-bibtex/) plugin, which allows you to export citations in BibTeX format and then manually update the citations in Overleaf. However, this requires manual steps and can bring inconsistencies if the bibliography is updated by multiple users.

This application allows you to link your Overleaf project with a Zotero library or collection, and update the citations in the project without requiring an Overleaf subscription. All credentials are used and stored locally.

![teaser](https://github.com/user-attachments/assets/3d7b7a7d-2728-48b6-a867-17f975109d18)

## Pre-requisites

1. Have a Zotero account (<https://www.zotero.org/>)
2. Have a Zotero library/collection with items you want to cite
3. Have an Overleaf account (<https://www.overleaf.com/>) and a project where you want to use the citations

## Python-based application

See the branch `python-archive`.

## Disclaimer

This application is not affiliated with Overleaf or Zotero. It is a third-party tool that uses the Overleaf Git API and Zotero web API to update citations in Overleaf projects. Use it at your own risk. The author is not responsible for any data loss or issues that may arise from using this tool.
