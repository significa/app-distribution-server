import plistlib
import zipfile


def get_app_info(ipa_file_path):
    with zipfile.ZipFile(ipa_file_path, 'r') as ipa:
        for file in ipa.namelist():
            if file.endswith('.app/Info.plist'):
                data = ipa.read(file)
                info = plistlib.loads(data)
                bundle_id = info.get('CFBundleIdentifier')
                app_title = info.get('CFBundleName')
                bundle_version = info.get('CFBundleShortVersionString')

                if (
                    bundle_id is None
                    or app_title is None
                    or bundle_version is None
                ):
                    raise RuntimeError("Failed to extract plist file information")

                return app_title, bundle_id, bundle_version

    raise RuntimeError("Could not find plist file in bundle")
