# ProGuard rules for MedConnect AI
# Keep WebView and its interfaces
-keepclassmembers class fqcn.of.javascript.interface.for.webview {
   public *;
}

-keepattributes JavascriptInterface
-keepattributes *Annotation*

# Keep database and other important classes
-keep class com.medconnectai.app.** { *; }

# standard android rules
-dontwarn android.webkit.**
