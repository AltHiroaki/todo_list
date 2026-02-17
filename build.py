import os
import shutil
import subprocess
import time

def build():
    # 1. PyInstallerの実行
    print("Running PyInstaller...")
    subprocess.run([
        "pyinstaller",
        "--noconsole",
        "--onefile",
        "--name", "SlideTasks",
        "main.py"
    ], check=True)

    # 2. 配布用フォルダの作成
    dist_dir = "dist"
    release_dir = os.path.join(dist_dir, "SlideTasks_v1.0")
    
    if os.path.exists(release_dir):
        shutil.rmtree(release_dir)
    os.makedirs(release_dir)
    print(f"Created release directory: {release_dir}")

    # 3. ファイルコピー
    # SlideTasks.exe
    exe_source = os.path.join(dist_dir, "SlideTasks.exe")
    exe_dest = os.path.join(release_dir, "SlideTasks.exe")
    if os.path.exists(exe_source):
        shutil.move(exe_source, exe_dest)
        print(f"Moved EXE to: {exe_dest}")
    else:
        print("Error: SlideTasks.exe not found!")
        return

    # credentials.json
    if os.path.exists("credentials.json"):
        shutil.copy("credentials.json", os.path.join(release_dir, "credentials.json"))
        print("Copied credentials.json")
    else:
        print("Warning: credentials.json not found.")

    # README.md
    if os.path.exists("README.md"):
        shutil.copy("README.md", os.path.join(release_dir, "README.md"))
        print("Copied README.md")

    # 4. データフォルダ作成
    data_dir = os.path.join(release_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    print("Created data directory")

    # 5. クリーンアップ
    print("Cleaning up...")
    if os.path.exists("build"):
        shutil.rmtree("build")
    
    spec_file = "SlideTasks.spec"
    if os.path.exists(spec_file):
        os.remove(spec_file)
    
    print("Done! Distribution package is ready at:", release_dir)

if __name__ == "__main__":
    build()
