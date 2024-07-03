# Simple iOS IPA App Distribution Server

This is a simple, self-hosted IPA app distribution server.

![Site and usage Preview](images/preview.png)

This server can be used for either Ad-hoc or Enterprise application distribution.
Developers can perform internal builds on their computers (without using a service like Expo)
and utilize this platform to easily distribute the build among other developers, testers,
or clients.

We wrote a blog post about this project, it explains the 'Why' and has a walkthrough on how to
use/deploy it (more 'How-to' style): [How to distribute iOS IPA builds][blog post].

The project provides a single endpoint for uploading an `.ipa` build. It returns a publicly
accessible, minimalistic installation page with a QR code - that simple. It is designed for easy
deployment within your infrastructure via a Docker container. And the upload functionality is
secured with a pre-shared authorization token (see "Configuration" below).

To maintain simplicity and focus, this project **does not** handle device ID registration or
application building.

## Usage

To run with Docker:

```sh
docker run \
  -p 8000:8000 \
  -v ipa-uploads:/uploads \
  -it ghcr.io/significa/ipa-app-distribution-server
```

To upload your first IPA app build (`your-app-build.ipa` in the working directory):

```
curl -X "POST" \
  "http://localhost:8000/upload" \
  -H "Accept: application/json" \
  -H "X-Auth-Token: secret" \
  -H "Content-Type: multipart/form-data" \
  -F "ipa_file=@your-app-build.ipa"
```

This will return a link to the installation page.

More documentation in the Swagger OpenAPI explorer available on `/docs`.

## Configuration

- `UPLOADS_SECRET_AUTH_TOKEN`: Token used for uploads. PLEASE CHANGE IT!
  Default: `secret`.

- `APP_BASE_URL`: The front-facing app URL for link generation.
  Defaults to `http://localhost:8000`.

- `STORAGE_URL`: A [PyFilesystem2](https://github.com/PyFilesystem/pyfilesystem2) compatible URL.
  Defaults to `osfs:///uploads` for Docker installations, and `osfs://./uploads` when running
  directly with Python. This means `/uploads` and `./uploads` respectively.  

  Compatible with many storage backends. Check out the possible configurations in the
  [index of filesystems](https://www.pyfilesystem.org/page/index-of-filesystems/).
  
  AWS S3 Example: `s3://your-bucket-name` (and then provide the credentials via the usual
  `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`).

## Development

**Requirements**:

- Python 3.11
- Make tools

**Useful development commands**:

- Setup a virtual environment (ex: `make setup-venv`).

- Install the dependencies: `make install-deps`.

- Start the development server: `make dev`.  
  Open the interactive OpenAPI explorer: http://localhost:3000/docs.

- When changes to the dependencies are made, freeze them in the lockfile with: `make lock-deps`.

## License

GNU GPLv3

---

Built by [Significa](https://significa.co)


[Blog post]: https://significa.co/blog/how-to-distribute-ios-ipa-builds
