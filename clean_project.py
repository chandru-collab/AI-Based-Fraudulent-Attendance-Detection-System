import os
import shutil

def clean_project():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Clear backend/uploads folder (keep the folder itself, but delete all test image contents)
    uploads_dir = os.path.join(root_dir, "backend", "uploads")
    if os.path.exists(uploads_dir):
        print(f"Cleaning test uploads directory: {uploads_dir}")
        for item in os.listdir(uploads_dir):
            item_path = os.path.join(uploads_dir, item)
            try:
                if os.path.isfile(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            except Exception as e:
                print(f"Error deleting {item_path}: {e}")
                
    # 2. Directories to remove completely (dev cache and ML training synthetic datasets)
    dirs_to_remove = [
        os.path.join(root_dir, ".pytest_cache"),
        os.path.join(root_dir, "ml_training"),
    ]
    
    def remove_readonly(func, path, excinfo):
        import stat
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            pass

    for d in dirs_to_remove:
        if os.path.exists(d):
            print(f"Removing directory: {d}")
            try:
                shutil.rmtree(d, onerror=remove_readonly)
            except Exception as e:
                print(f"Error removing {d}: {e}")
                
    # 3. Development utilities, logs, and unused launch scripts to remove
    files_to_remove = [
        os.path.join(root_dir, "SKILL.md"),
        os.path.join(root_dir, "check_db.py"),
        os.path.join(root_dir, "check_port.py"),
        os.path.join(root_dir, "patch-fs.js"),
        os.path.join(root_dir, "backend_err.log"),
        os.path.join(root_dir, "backend_out.log"),
        os.path.join(root_dir, "service-account-key.json"),
        os.path.join(root_dir, "frontend", "dev.js"),
        os.path.join(root_dir, "frontend", "dev.cjs"),
        os.path.join(root_dir, "frontend", "vite_err.log"),
        os.path.join(root_dir, "frontend", "vite_out.log"),
    ]
    
    for f in files_to_remove:
        if os.path.exists(f):
            print(f"Removing file: {f}")
            try:
                os.remove(f)
            except Exception as e:
                print(f"Error removing {f}: {e}")
                
    print("\nProject cleaning complete! Ready for production deployment.")

if __name__ == "__main__":
    clean_project()
