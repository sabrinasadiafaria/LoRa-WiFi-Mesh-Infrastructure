import os
import shutil
import sys

def main():
    print("SAR Rescue Phase 10 - Asset Copy Script")
    src = "../../phase 9/pi/dashboard/leaflet"
    dst = "dashboard/leaflet"
    
    if os.path.exists(src):
        if not os.path.exists(dst):
            print(f"Copying {src} to {dst}")
            shutil.copytree(src, dst)
            print("Assets copied successfully.")
        else:
            print("Assets already exist in destination.")
    else:
        print("Warning: Source leaflet directory not found.")
        print("Expected to find it at: " + os.path.abspath(src))

if __name__ == "__main__":
    main()
