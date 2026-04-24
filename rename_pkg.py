import os
import shutil

old_pkg = "com.medconnectai.app"
new_pkg = "com.shravan.easymedchoice"

old_path = os.path.join("MedConnectMobile", "app", "src", "main", "java", "com", "medconnectai", "app")
new_path_dir = os.path.join("MedConnectMobile", "app", "src", "main", "java", "com", "shravan", "easymedchoice")
base_to_delete = os.path.join("MedConnectMobile", "app", "src", "main", "java", "com", "medconnectai")

os.makedirs(new_path_dir, exist_ok=True)

# Move java files
if os.path.exists(old_path):
    for filename in os.listdir(old_path):
        if filename.endswith(".java"):
            shutil.move(os.path.join(old_path, filename), os.path.join(new_path_dir, filename))

# Delete old tree
if os.path.exists(base_to_delete):
    shutil.rmtree(base_to_delete)

# Replace in files
files_to_update = [
    os.path.join("MedConnectMobile", "app", "build.gradle"),
    os.path.join("MedConnectMobile", "app", "src", "main", "AndroidManifest.xml")
]
for root, dirs, files in os.walk(new_path_dir):
    for file in files:
        if file.endswith(".java"):
            files_to_update.append(os.path.join(root, file))

for filepath in files_to_update:
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace(old_pkg, new_pkg)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

print("Package rename success.")
