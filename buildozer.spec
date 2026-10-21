[app]
title = Mega-Sena AI V3
package.name = megasenaai
package.domain = com.wmox
source.dir = .
source.include_exts = py,json,png,jpg,kv,atlas
icon.filename = %(source.dir)s/icon.png
version = 3.1
requirements = python3,kivy,numpy,requests
orientation = portrait
fullscreen = 0
android.api = 35
android.minapi = 23
android.archs = arm64-v8a,armeabi-v7a
android.permissions = INTERNET

[buildozer]
log_level = 2
warn_on_root = 1

[app:android]
android.sdk_path = /usr/local/lib/android/sdk
android.ndk_path = /usr/local/lib/android/sdk/ndk/28.2.13676358
