[app]
# (str) Title of your application
title = Posture Monitor

# (str) Package name
package.name = posture_monitor

# (str) Package domain (needed for android/ios packaging)
package.domain = org.posture.monitor

# (source.dir) Source code directory where the main.py lives
source.dir = .

# (list) Source include patterns (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,ogg,wav

# (list) List of inclusions using pattern matching
#source.include_patterns = assets/*,images/*.png

# (list) Source exclude patterns
#source.exclude_exts = spec

# (list) List of directory to exclude from check source.include_patterns
#source.exclude_dirs = tests, bin

# (list) List of exclusions using pattern matching
#source.exclude_patterns = license,images/*/*.jpg

# (str) Application versioning (method 1)
version = 1.0.0

# (str) Application versioning (method 2)
# version.regex = __version__ = ['"](.*)['"]
# version.filename = %(source.dir)s/main.py

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
requirements = python3,kivy,paho-mqtt

# (str) Supported orientation (landscape, portrait or all)
orientation = portrait

# (list) List of service to declare
#services = MyService:myservice.py

#############################################
# Android specific
#############################################

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (str) Permissions
# See https://developer.android.com/guide/topics/permissions/overview
# Format: PERMISSION,PERMISSION2
android.permissions = INTERNET

# (list) Android arcitectures to build for, choices: armeabi-v7a, arm64-v8a, x86, x86_64
android.archs = arm64-v8a

# (bool) Indicate if the application should be fullscreen or not
android.fullscreen = 0

# (str) Android app theme, default is ok for Kivy-based application
# android.theme = "@android:style/Theme.NoTitleBar"

# (bool) Copy library instead of making a libpymodules.so
android.copy_libs = 1

# (str) The Android arch to build for, choices: armeabi-v7a, arm64-v8a, x86, x86_64
# In general, you hardware is always compatible.
# If unspecified, will default to 'arm64-v8a'.
# android.ndk = '25c'

# (bool) Use the new toolchain
android.gradle_dependencies = 

# (str) Android logcat filters to use
#android.logcat_filters = *:S python:D

# (bool) Copy library instead of making a libpymodules.so
#android.copy_libs = 1

# (str) The Android arch to build for, choices: armeabi-v7a, arm64-v8a, x86, x86_64
android.ndk = 25b

# (bool) Enable AndroidX support
android.enable_androidx = True

# (str) Android API to use
android.api = 31

# (str) Minimum API to use
android.minapi = 21

# (str) Android NDK version to use
#android.ndk_version = 25b

# (bool) Use legacy build or not. You probably want to keep it as False (the default)
#android.use_legacy_toolchain = False

# (bool) Enable AndroidX support
#android.enable_androidx = True

#############################################
# Python for android (p4a) specific
#############################################

# (str) python for android URL, defaults to the one specified in server.py
#p4a.url = http://nightlies.kivy.org/downloads/buildozer/

# (int) port number to specify an explicit --port argument (eg for bootstrap flask)
#p4a.port = 5000

#############################################
# iOS specific
#############################################

# (bool) Set to True to create a Release certificate instead of a Debug one
ios.release_artifact = False

# (str) Path to codesign key
#ios.codesign_key = %(home)s/.ssh/android.keystore

# (str) Filename of HTTPS Server Certificate and Key as a and filename pair
#ios.codesign_key = %(home)s/.ssh/android.keystore, %(home)s/.ssh/android.keystore

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning upon buildozer run if given buildozer.spec is in dir of
# buildozer.spec with update in spec. (0 = disable)
warn_on_root = 1

# (str) Path to build artifact storage, absolute or relative to spec file
# build_dir = ./.buildozer

# (str) Path to build artifact storage, absolute or relative to spec file
# bin_dir = ./bin
