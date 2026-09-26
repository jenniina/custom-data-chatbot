# Import from personal OneDrive

## Public sharing links

1. Share the individual DOCX or converted JSON using **Anyone with the link**, view permission and downloads allowed.
2. Sign in as administrator in **Menu → Administrator sign-in**.
3. Open **Convert or import**, paste the sharing link under **Import a public OneDrive file**, then choose **Review OneDrive document**.
4. Review the text and select **Add to chatbot library**.
5. Optionally download JSON and save it to your OneDrive folder.

No Microsoft app registration or login is required. `ONEDRIVE_PUBLIC_URL` optionally prefills the administrator's link field; it is not shown to public readers.

Some viewer, expired or restricted links cannot be downloaded anonymously. In that case, download the file yourself and upload it through the same page. The app does not index a Microsoft login page as a document.

Anyone with a public link can read its source file. Chat visitors can learn indexed information through answers. OneDrive edits are not automatically published: import the new version and remove the old one.

Microsoft's [sharing guide](https://support.microsoft.com/en-us/onedrive/share-files-and-folders-in-microsoft-onedrive) explains link permissions.

## Optional private connection

The existing Microsoft device-code flow is retained. To configure it:

1. Create an application in [Microsoft Entra app registrations](https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade). This requires access to a tenant where you can register applications.
2. Allow personal Microsoft accounts.
3. Enable **Allow public client flows** in Authentication.
4. Add Microsoft Graph's delegated **Files.Read** permission. No client secret or write permission is needed.
5. Set `ONEDRIVE_CLIENT_ID` in your private server environment or local `.env`.

Then choose **Convert or import → Connect to a private OneDrive file instead**. Select **Connect OneDrive**, open Microsoft's sign-in page, enter the displayed code and sign in. Return and select **I have completed Microsoft sign-in**.

Enter a path relative to your OneDrive root, such as `ContextMe/profile.docx`. Choose **Review private document**, review the result, then **Add to chatbot library**. JSON download is optional. The app cannot write files back to OneDrive.

## Sessions and storage

Microsoft token caches are now stored in Django's private server-side session database. They are not sent in browser cookies or included in Git. This differs from the former Streamlit in-memory session. Protect the data directory and backups; the app does not encrypt the database.

Disconnecting or signing out removes the current connection. Sessions expire after one hour without modification; expired database rows are removed by `python manage.py clearsessions`, which also runs at startup. Disconnecting does not revoke Microsoft's consent grant.

OneDrive stores source documents, not the running search database. Readers do not need Microsoft access. For persistent hosting and Cloud Run limitations, see [DEPLOYMENT.md](DEPLOYMENT.md).

Microsoft references: [public client configuration](https://learn.microsoft.com/en-us/entra/identity-platform/scenario-desktop-app-configuration), [MSAL tokens](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens), [file downloads](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0).
