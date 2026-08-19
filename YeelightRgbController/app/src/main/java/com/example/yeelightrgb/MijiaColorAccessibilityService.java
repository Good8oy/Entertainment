package com.example.yeelightrgb;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.graphics.drawable.GradientDrawable;
import android.hardware.HardwareBuffer;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.DisplayMetrics;
import android.view.Display;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.lang.ref.WeakReference;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Finds and taps a requested RGB only within the user-calibrated Mi Home colour rectangle. */
public final class MijiaColorAccessibilityService extends AccessibilityService {
    static final String MI_HOME_PACKAGE = "com.xiaomi.smarthome";
    private static final int MAX_CHANNEL_DIFFERENCE = 18;
    private static WeakReference<MijiaColorAccessibilityService> current = new WeakReference<>(null);

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService scanExecutor = Executors.newSingleThreadExecutor();
    private WindowManager windowManager;
    private View floatingView;
    private WindowManager.LayoutParams floatingParams;
    private String foregroundPackage = "";

    @Override
    public void onServiceConnected() {
        super.onServiceConnected();
        current = new WeakReference<>(this);
        windowManager = (WindowManager) getSystemService(WINDOW_SERVICE);
        showBubble();
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        if (event.getPackageName() != null && !getPackageName().contentEquals(event.getPackageName())) {
            foregroundPackage = event.getPackageName().toString();
        }
    }

    @Override
    public void onInterrupt() {
        // No continuous interaction is in progress.
    }

    @Override
    public boolean onUnbind(android.content.Intent intent) {
        cleanup();
        return super.onUnbind(intent);
    }

    @Override
    public void onDestroy() {
        cleanup();
        super.onDestroy();
    }

    static boolean isReady() {
        return current.get() != null;
    }

    private void cleanup() {
        removeFloatingView();
        scanExecutor.shutdownNow();
        if (current.get() == this) {
            current = new WeakReference<>(null);
        }
    }

    private void showBubble() {
        removeFloatingView();
        TextView bubble = new TextView(this);
        bubble.setText("找色");
        bubble.setTextColor(Color.WHITE);
        bubble.setTextSize(15);
        bubble.setGravity(Gravity.CENTER);
        GradientDrawable background = new GradientDrawable();
        background.setColor(Color.rgb(25, 118, 210));
        background.setCornerRadius(dp(28));
        bubble.setBackground(background);
        bubble.setElevation(dp(6));
        bubble.setOnTouchListener(new BubbleTouchListener());

        floatingView = bubble;
        floatingParams = overlayParams(dp(58), dp(58));
        floatingParams.gravity = Gravity.END | Gravity.CENTER_VERTICAL;
        floatingParams.x = dp(10);
        windowManager.addView(floatingView, floatingParams);
    }

    private void showPicker() {
        removeFloatingView();
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(10), dp(10), dp(10), dp(10));
        GradientDrawable background = new GradientDrawable();
        background.setColor(Color.WHITE);
        background.setCornerRadius(dp(14));
        panel.setBackground(background);
        panel.setElevation(dp(8));

        PresetStore.RgbTarget target = PresetStore.loadTarget(this);
        TextView title = new TextView(this);
        title.setText("目标 RGB(" + target.red + ", " + target.green + ", " + target.blue + ")");
        title.setTextColor(Color.DKGRAY);
        title.setTextSize(16);
        title.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        panel.addView(title);

        Button find = new Button(this);
        find.setText("识别并点击目标 RGB");
        find.setAllCaps(false);
        find.setTextColor(Color.DKGRAY);
        find.setOnClickListener(v -> findAndTap(target));
        panel.addView(find);

        Button close = new Button(this);
        close.setText("收起");
        close.setAllCaps(false);
        close.setOnClickListener(v -> showBubble());
        panel.addView(close);

        floatingView = panel;
        floatingParams = overlayParams(dp(230), WindowManager.LayoutParams.WRAP_CONTENT);
        floatingParams.gravity = Gravity.END | Gravity.CENTER_VERTICAL;
        floatingParams.x = dp(10);
        windowManager.addView(floatingView, floatingParams);
    }

    private void findAndTap(PresetStore.RgbTarget target) {
        if (!isMiHomeColourPage()) {
            toast("请先停留在米家该灯的颜色色盘页面。 ");
            showBubble();
            return;
        }
        PresetStore.ColourRegion region = PresetStore.loadRegion(this);
        if (!region.isValid()) {
            toast("请先在助手中校准安全色盘区域。 ");
            showBubble();
            return;
        }
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) {
            toast("此功能需要 Android 11 或更新版本。 ");
            showBubble();
            return;
        }
        DisplayMetrics metrics = new DisplayMetrics();
        windowManager.getDefaultDisplay().getRealMetrics(metrics);
        float currentAspect = metrics.widthPixels / (float) metrics.heightPixels;
        float referenceAspect = region.referenceWidth / (float) region.referenceHeight;
        if (Math.abs(currentAspect - referenceAspect) > 0.01f) {
            toast("当前屏幕比例与校准截图不同，请重新校准。 ");
            showBubble();
            return;
        }
        removeFloatingView();
        handler.postDelayed(() -> captureAndFind(target, region), 120);
    }

    private void captureAndFind(PresetStore.RgbTarget target, PresetStore.ColourRegion region) {
        takeScreenshot(Display.DEFAULT_DISPLAY, scanExecutor, new TakeScreenshotCallback() {
            @Override
            public void onSuccess(ScreenshotResult screenshotResult) {
                Bitmap bitmap = null;
                HardwareBuffer buffer = null;
                try {
                    buffer = screenshotResult.getHardwareBuffer();
                    Bitmap hardwareBitmap = Bitmap.wrapHardwareBuffer(buffer, screenshotResult.getColorSpace());
                    if (hardwareBitmap == null) {
                        throw new IllegalStateException("无法读取当前屏幕。 ");
                    }
                    bitmap = hardwareBitmap.copy(Bitmap.Config.ARGB_8888, false);
                    hardwareBitmap.recycle();
                    buffer.close();
                    buffer = null;
                    Match match = findClosestMatch(bitmap, region, target);
                    bitmap.recycle();
                    bitmap = null;
                    handler.post(() -> finishFind(match, target));
                } catch (RuntimeException error) {
                    if (bitmap != null) {
                        bitmap.recycle();
                    }
                    if (buffer != null) {
                        buffer.close();
                    }
                    handler.post(() -> {
                        toast("找色失败：" + friendlyMessage(error));
                        showBubble();
                    });
                }
            }

            @Override
            public void onFailure(int errorCode) {
                handler.post(() -> {
                    toast("系统拒绝屏幕截图（错误 " + errorCode + "）。 ");
                    showBubble();
                });
            }
        });
    }

    private void finishFind(Match match, PresetStore.RgbTarget target) {
        if (match == null) {
            toast("安全区域内未找到足够接近 RGB(" + target.red + ", " + target.green + ", " + target.blue + ") 的像素；未执行点击。 ");
            showBubble();
            return;
        }
        boolean sent = dispatchTap(match.x, match.y);
        toast(sent ? "已在安全区域点击 RGB 匹配点。" : "手势未被系统接受。 ");
        showBubble();
    }

    private Match findClosestMatch(Bitmap bitmap, PresetStore.ColourRegion region, PresetStore.RgbTarget target) {
        int left = clamp(Math.round(region.left * (bitmap.getWidth() / (float) region.referenceWidth)), 0, bitmap.getWidth() - 1);
        int top = clamp(Math.round(region.top * (bitmap.getHeight() / (float) region.referenceHeight)), 0, bitmap.getHeight() - 1);
        int right = clamp(Math.round(region.right * (bitmap.getWidth() / (float) region.referenceWidth)), left + 1, bitmap.getWidth());
        int bottom = clamp(Math.round(region.bottom * (bitmap.getHeight() / (float) region.referenceHeight)), top + 1, bitmap.getHeight());

        int[] row = new int[right - left];
        Match best = null;
        for (int y = top; y < bottom; y++) {
            bitmap.getPixels(row, 0, row.length, left, y, row.length, 1);
            for (int index = 0; index < row.length; index++) {
                int colour = row[index];
                int redDifference = Math.abs(Color.red(colour) - target.red);
                int greenDifference = Math.abs(Color.green(colour) - target.green);
                int blueDifference = Math.abs(Color.blue(colour) - target.blue);
                int maximumDifference = Math.max(redDifference, Math.max(greenDifference, blueDifference));
                int distance = redDifference * redDifference + greenDifference * greenDifference + blueDifference * blueDifference;
                if (best == null || distance < best.distance) {
                    best = new Match(left + index, y, distance, maximumDifference);
                }
            }
        }
        return best != null && best.maximumDifference <= MAX_CHANNEL_DIFFERENCE ? best : null;
    }

    private boolean isMiHomeColourPage() {
        if (!MI_HOME_PACKAGE.equals(foregroundPackage)) {
            AccessibilityNodeInfo root = getRootInActiveWindow();
            if (root == null || root.getPackageName() == null || !MI_HOME_PACKAGE.contentEquals(root.getPackageName())) {
                return false;
            }
        }
        AccessibilityNodeInfo root = getRootInActiveWindow();
        return root != null && containsColourLabel(root, 0);
    }

    private boolean containsColourLabel(AccessibilityNodeInfo node, int depth) {
        if (depth > 30) {
            return false;
        }
        if (containsColour(node.getText()) || containsColour(node.getContentDescription())) {
            return true;
        }
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            if (child != null && containsColourLabel(child, depth + 1)) {
                return true;
            }
        }
        return false;
    }

    private boolean containsColour(CharSequence text) {
        if (text == null) {
            return false;
        }
        String value = text.toString();
        return value.contains("颜色") || value.contains("顏色") || value.contains("色温")
                || value.contains("色溫") || value.toLowerCase().contains("color");
    }

    private boolean dispatchTap(int x, int y) {
        Path path = new Path();
        path.moveTo(x, y);
        GestureDescription gesture = new GestureDescription.Builder()
                .addStroke(new GestureDescription.StrokeDescription(path, 0, 80))
                .build();
        return dispatchGesture(gesture, null, null);
    }

    private void removeFloatingView() {
        if (floatingView != null && windowManager != null) {
            try {
                windowManager.removeView(floatingView);
            } catch (IllegalArgumentException ignored) {
                // The system may have already detached the overlay.
            }
            floatingView = null;
        }
    }

    private WindowManager.LayoutParams overlayParams(int width, int height) {
        return new WindowManager.LayoutParams(width, height,
                WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
                PixelFormat.TRANSLUCENT);
    }

    private int clamp(int value, int minimum, int maximum) {
        return Math.max(minimum, Math.min(maximum, value));
    }

    private String friendlyMessage(Exception error) {
        return error.getMessage() == null ? error.getClass().getSimpleName() : error.getMessage();
    }

    private void toast(String message) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show();
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    private static final class Match {
        final int x;
        final int y;
        final int distance;
        final int maximumDifference;

        Match(int x, int y, int distance, int maximumDifference) {
            this.x = x;
            this.y = y;
            this.distance = distance;
            this.maximumDifference = maximumDifference;
        }
    }

    private final class BubbleTouchListener implements View.OnTouchListener {
        private float startRawX;
        private float startRawY;
        private int startX;
        private int startY;
        private boolean dragged;

        @Override
        public boolean onTouch(View view, MotionEvent event) {
            switch (event.getAction()) {
                case MotionEvent.ACTION_DOWN:
                    startRawX = event.getRawX();
                    startRawY = event.getRawY();
                    startX = floatingParams.x;
                    startY = floatingParams.y;
                    dragged = false;
                    return true;
                case MotionEvent.ACTION_MOVE:
                    float dx = event.getRawX() - startRawX;
                    float dy = event.getRawY() - startRawY;
                    if (Math.abs(dx) > dp(4) || Math.abs(dy) > dp(4)) {
                        dragged = true;
                    }
                    floatingParams.x = startX - Math.round(dx);
                    floatingParams.y = startY + Math.round(dy);
                    windowManager.updateViewLayout(floatingView, floatingParams);
                    return true;
                case MotionEvent.ACTION_UP:
                    if (!dragged) {
                        showPicker();
                    }
                    return true;
                default:
                    return true;
            }
        }
    }
}
