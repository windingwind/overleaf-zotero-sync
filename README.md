# Link Overleaf project with Zotero

![teaser](https://github.com/user-attachments/assets/3d7b7a7d-2728-48b6-a867-17f975109d18)

## Pre-requisites

1. Have a Zotero account (<https://www.zotero.org/>)
2. Have a Zotero library/collection with items you want to cite
3. Have an Overleaf account (<https://www.overleaf.com/>) and a project where you want to use the citations
4. Download the executable file from the [Release page](https://github.com/windingwind/overleaf-zotero-sync/releases/latest)

> [!note]
>
> - Zotero desktop app is not required for updating citations in Overleaf
> - Overleaf subscription is not required

## Steps to link Overleaf with Zotero

> [!note]
>
> - The credentials will be stored in your local `~/.config/zotero_overleaf/config.json` file. You only need to setup credentials once.
> - Multiple Overleaf project links and their corresponding Zotero libraries can be stored in the same file. The application will prompt you to select the project you want to update citations for.

### Prepare Overleaf project

1. Open the Overleaf project where you want to use the citations
2. Click on the "Menu" button in the top left corner
3. Click on the "Sync" -> "Git"
4. Copy the Git URL of the project. If you don't have a credential created yet, click on "Generate token" to create one and copy the token as well

### Prepare Zotero library

1. Open the Zotero web library (<https://www.zotero.org/mylibrary/>)
2. In the left pane, select the library or collection you want to use for citations
3. Copy the URL of the library or collection from the address bar of your browser. It should look like one of the following formats:

   ```txt
   https://www.zotero.org/$username/library
   https://www.zotero.org/$username/collections/$collectionID
   https://www.zotero.org/groups/$groupName/library
   https://www.zotero.org/groups/$groupName/collections/$collectionID
   ```

### Run the executable

1. Execute the downloaded file (double-click or run from terminal)
2. If you are running it for the first time, it will prompt you to enter the Overleaf token, project name, Overleaf Git URL, and Zotero library URL
   > [!note]
   > If you are using a group library, you will need to authorize the application to read access to the group library.
3. If you have already set up the credentials, it will prompt you to select the project you want to update citations for
4. Wait for the application to finish updating the citations in the Overleaf project

## Disclaimer

This application is not affiliated with Overleaf or Zotero. It is a third-party tool that uses the Overleaf Git API and Zotero web API to update citations in Overleaf projects. Use it at your own risk. The author is not responsible for any data loss or issues that may arise from using this tool.
