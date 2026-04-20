# easyMed - Android WebView App

This is the Android mobile app version of the easyMed telemedicine platform. It uses a `WebView` to wrap the existing web platform, providing a standalone mobile experience with support for file uploads and medical report management.

## Project Structure
- `app/src/main/java/com/easyMedai/app/MainActivity.java`: Core WebView logic.
- `app/src/main/AndroidManifest.xml`: Permissions and App configuration.
- `app/src/main/res/layout/activity_main.xml`: Main UI layout.
- `build.gradle` & `settings.gradle`: Android build configuration.

## Setup Instructions

1. **Install Android Studio**: Download and install [Android Studio](https://developer.android.com/studio).
2. **Open the Project**:
   - Open Android Studio.
   - Select **Open an Existing Project**.
   - Navigate to the `easyMedMobile` folder I created in your project root.
3. **Configure the URL**:
   - Open `app/src/main/java/com/easyMedai/app/MainActivity.java`.
   - Update the `APP_URL` variable to your server's IP address.
   - *Note*: If running locally on an emulator, use `http://10.0.2.2:5000`.
4. **Build and Run**:
   - Connect an Android device or start an emulator.
   - Click the **Run** button (green play icon) in Android Studio.

## Deployment Guide

### Option A: Render.com (Easiest)
1.  **Prepare your code**: Ensure all changes are committed to your GitHub repository.
2.  **Create a Web Service**:
    - Build System: **Python**
    - Build Command: `pip install -r requirements.txt`
    - Start Command: `gunicorn --worker-class eventlet -w 1 app:app`
3.  **Environment Variables**:
    - `SECRET_KEY`: A long random string.

### Option B: AWS (Amazon Web Services)
For a professional medical platform, AWS is a great choice.

#### Using AWS App Runner (Recommended)
1.  **Connect Repo**: Connect your GitHub repository to AWS App Runner.
2.  **Configuration**:
    - Runtime: **Python 3**
    - Build command: `pip install -r requirements.txt`
    - Start command: `python app.py` (or `gunicorn --worker-class eventlet -w 1 app:app`)
    - Port: **5000**
3.  **Security**: App Runner provides automatic HTTPS.

#### Using AWS Elastic Beanstalk
1.  **Initialize**: Use the EB CLI to create a new environment.
2.  **Load Balancer**: Ensure you use an **Application Load Balancer** (ALB) to support WebSockets (SocketIO).
3.  **Config**: Set the environment variable `FLASK_APP=app.py`.

## Features
- **Persistent Login**: Uses DOM Storage to remember your session and theme preference.
- **File Upload**: Handles medical report uploads through the native file picker.
- **Navigation**: Integrated back-button support for a seamless mobile experience.
- **Dark Mode**: Fully supports the platform's Dark mode toggle.
