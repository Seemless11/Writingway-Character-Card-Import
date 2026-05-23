# .spec file for use with pyinstaller.
# This creates a standalone distribution of Writingway with python and all dependencies included
#
# Use:
# 1. Install Writingway first (e.g. run setup_writingway.sh)
# 2. Activate the venv
# 3. Install pyinstaller: pip install pyinstaller
# 4. Run pyinstaller: pyinstaller Writingway.spec
# 5. The output is in the dist folder.
import shutil

from PyInstaller.building.api import COLLECT
from PyInstaller.building.datastruct import Tree
from pathlib import Path
from PyInstaller.utils.hooks import collect_all
import os

ApplicationName = 'Writingway'

# Additional files to add to the _internal directory
datas = [
]

binaries = []
hiddenimports = ['tiktoken_ext.openai_public', 'tiktoken_ext', 'pyaudio']

# wrap collect_all to make it log what it did
def _collect_all(pkg):
    """Run collect_all and merge results into datas/binaries/hiddenimports."""
    global datas, binaries, hiddenimports
    try:
        pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hiddenimports
        print(f"collect_all({pkg!r}): "
              f"{len(pkg_datas)} datas, "
              f"{len(pkg_binaries)} binaries, "
              f"{len(pkg_hiddenimports)} hiddenimports")
    except Exception as e:
        print(f"collect_all({pkg!r}) skipped: {e}")

# Do a collect_all (which does a copy_metadata internally) for the packages below.
_collect_all('cmudict') # cmudict ships data files that must be bundled
_collect_all('imageio')
_collect_all('langchain_ollama')

a = Analysis(
    ['../main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# Get the target_arch from the environment. For OSX valid options are "arm64", "x86_64" and "universal2"
target_arch=os.environ.get('TARGET_ARCH')
if target_arch is not None:
    print(f"TARGET_ARCH={target_arch}")

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='main', # Name of the executable
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    codesign_identity=None,
    entitlements_file=None,
    # If the TARGET_ARCH environment variable is set, add a target_arch to this call to EXE()

    target_arch=target_arch
    # contents_directory='_internal'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=ApplicationName,
)

# Files to add to the root (i.e. where the executable is) instead of the _internal directory
root_files = [
# Project
'MyFirstProject_structure.json',
'project_settings.json',
'prompts_MyFirstProject.json',

# App version
'version.json',

# Documentation
'README.md',
'Writingway_Introduction.docx',
'Writingway_TLDR.docx',
]

# Create a root_tree array of the files to add to the collection: [ (dest, source, DATA), ... ]
# Add the Writingway assets directory
root_tree = Tree('assets', 'assets')
# Add the startup script
root_tree += [('Writingway', 'pyinstaller/Writingway', 'DATA')]
# Add files from the Writingway root that we want to ship. We're in a subdirectory, so we need to add '../'
for f in root_files:
    root_tree += [(f, f, 'DATA')]

# I Can't find a way to let pyinstaller handle the copying, so copy the files manually.
dist_path = Path(DISTPATH) / ApplicationName

for dest_name, source_path, _ in root_tree:
    src_path = Path(source_path)
    dst_path = dist_path / dest_name

    if src_path.exists():
        # Create destination directory if needed
        dst_path.parent.mkdir(parents=True, exist_ok=True)

        if src_path.is_file():
            shutil.copy2(src_path, dst_path)

        print(f"Copied {src_path} to {dst_path}")
    else:
        print(f"Warning: File not found: {src_path}")
