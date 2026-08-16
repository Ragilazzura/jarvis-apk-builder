plugins {
    id("com.android.application")
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.example.jarvis_agent"
    compileSdk = 36 // 👈 Dinaikkan ke 36 untuk meredam protes seluruh plugin modern
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        isCoreLibraryDesugaringEnabled = true
    }

    defaultConfig {
        applicationId = "com.stark.jarvis"
        minSdk = flutter.minSdkVersion
        targetSdk = 36 // 👈 Diselaraskan ke 36
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    // 🛡️ Mengatasi konflik duplikat file .so dari onnxruntime & open_wake_word
    packaging {
        jniLibs {
            pickFirsts.add("lib/arm64-v8a/libonnxruntime.so")
            pickFirsts.add("lib/armeabi-v7a/libonnxruntime.so")
            pickFirsts.add("lib/x86_64/libonnxruntime.so")
            pickFirsts.add("lib/x86/libonnxruntime.so")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

flutter {
    source = "../.."
}

dependencies {
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")
}