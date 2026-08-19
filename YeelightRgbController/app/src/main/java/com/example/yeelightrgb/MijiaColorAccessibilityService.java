package com.example.yeelightrgb;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.graphics.drawable.GradientDrawable;
import android.os.Handler;
import android.os.Looper;
import android.util.DisplayMetrics;
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
import java.util.List;

/**
 * Hosts the colour-card overlay and emits one calibrated tap only while the Mi Home colour page is active.
 */
public final class MijiaColorAccessibilityService extends AccessibilityService {
    static final String MI_HOME_PACKAGE = "com.xiaomi.smarthome";
    private static WeakReference<MijiaColorAccessibilityService> current = new WeakReference<>(null);

    private final Handler handler = new Handler(Looper.getMainLooper());
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
    public boolean onUnbind(Intent intent) {
        removeFloatingView();
        if (current.get() == this) {
            current = new WeakReference<>(null);
        }
        return super.onUnbind(intent);
    }

    @Override
    public void onDestroy() {
        removeFloatingView();
        if (current.get() == this) {
            current = new WeakReference<>(null);
        }
        super.onDestroy();
    }

    static boolean isReady() {
        return current.get() != null;
    }

    private void showBubble() {
        removeFloatingView();
        TextView bubble = new TextView(this);
        bubble.setText("色卡");
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

    private void showPalette() {
        removeFloatingView();
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(10), dp(10), dp(10), dp(10));
        GradientDrawable background = new GradientDrawable();
        background.setColor(Color.WHITE);
        background.setCornerRadius(dp(14));
        panel.setBackground(background);
        panel.setElevation(dp(8));

        TextView title = new TextView(this);
        title.setText("米家色卡");
        title.setTextColor(Color.DKGRAY);
        title.setTextSize(16);
        title.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        panel.addView(title);

        PresetStore.ManualColour manualColour = PresetStore.loadManualColour(this);
        Button manualOption = new Button(this);
        manualOption.setText("应用手动 RGB\n(" + manualColour.red + ", " + manualColour.green + ", "
                + manualColour.blue + ") · 亮度 " + manualColour.brightness + "%");
        manualOption.setTextColor(Color.DKGRAY);
        manualOption.setAllCaps(false);
        manualOption.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
        GradientDrawable manualBackground = new GradientDrawable();
        manualBackground.setColor(manualColour.previewColour());
        manualBackground.setAlpha(70);
        manualBackground.setCornerRadius(dp(8));
        manualOption.setBackground(manualBackground);
        manualOption.setOnClickListener(v -> applyManualColour(manualColour));
        LinearLayout.LayoutParams manualParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        manualParams.topMargin = dp(6);
        panel.addView(manualOption, manualParams);

        List<PresetStore.Preset> presets = PresetStore.load(this);
        if (presets.isEmpty()) {
            TextView empty = new TextView(this);
            empty.setText("请先在助手中从截图校准色卡。 ");
            empty.setTextColor(Color.DKGRAY);
            empty.setPadding(0, dp(8), 0, dp(4));
            panel.addView(empty);
        } else {
            for (PresetStore.Preset preset : presets) {
                Button option = new Button(this);
                option.setText(preset.name);
                option.setTextColor(Color.DKGRAY);
                option.setAllCaps(false);
                option.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
                GradientDrawable optionBackground = new GradientDrawable();
                optionBackground.setColor(preset.previewColor);
                optionBackground.setAlpha(70);
                optionBackground.setCornerRadius(dp(8));
                option.setBackground(optionBackground);
                option.setOnClickListener(v -> applyPreset(preset));
                LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.MATCH_PARENT,
                        LinearLayout.LayoutParams.WRAP_CONTENT
                );
                params.topMargin = dp(6);
                panel.addView(option, params);
            }
        }

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

    private void applyPreset(PresetStore.Preset preset) {
        if (!isMiHomeColourPage()) {
            toast("请先停留在米家该灯的“颜色”色盘页面。 ");
            showBubble();
            return;
        }
        DisplayMetrics metrics = new DisplayMetrics();
        windowManager.getDefaultDisplay().getRealMetrics(metrics);
        float currentAspect = metrics.widthPixels / (float) metrics.heightPixels;
        float referenceAspect = preset.referenceWidth / (float) preset.referenceHeight;
        if (Math.abs(currentAspect - referenceAspect) > 0.01f) {
            toast("当前屏幕比例与校准截图不同，请重新校准。 ");
            showBubble();
            return;
        }
        int x = Math.round(preset.x * (metrics.widthPixels / (float) preset.referenceWidth));
        int y = Math.round(preset.y * (metrics.heightPixels / (float) preset.referenceHeight));
        removeFloatingView();
        handler.postDelayed(() -> {
            boolean sent = dispatchTap(x, y);
            toast(sent ? "已选择：" + preset.name : "手势未被系统接受。 ");
            showBubble();
        }, 120);
    }

    private void applyManualColour(PresetStore.ManualColour manualColour) {
        if (!isMiHomeColourPage()) {
            toast("请先停留在米家该灯的“颜色”色盘页面。 ");
            showBubble();
            return;
        }
        PresetStore.Mapping mapping = PresetStore.loadMapping(this);
        if (!mapping.hasColourBounds() || !mapping.hasBrightnessBounds()) {
            toast("请先在助手中完成色盘与亮度滑杆校准。 ");
            showBubble();
            return;
        }
        DisplayMetrics metrics = new DisplayMetrics();
        windowManager.getDefaultDisplay().getRealMetrics(metrics);
        if (!hasMatchingAspect(metrics, mapping.colourWidth, mapping.colourHeight)
                || !hasMatchingAspect(metrics, mapping.brightnessWidth, mapping.brightnessHeight)) {
            toast("当前屏幕比例与校准截图不同，请重新校准。 ");
            showBubble();
            return;
        }

        float[] hsv = new float[3];
        Color.RGBToHSV(manualColour.red, manualColour.green, manualColour.blue, hsv);
        int colourX = Math.round(scaleX(mapping.left + (hsv[0] / 360f) * (mapping.right - mapping.left),
                metrics.widthPixels, mapping.colourWidth));
        int colourY = Math.round(scaleY(mapping.top + (1f - hsv[1]) * (mapping.bottom - mapping.top),
                metrics.heightPixels, mapping.colourHeight));
        float brightnessRatio = manualColour.brightness / 100f;
        int brightnessX = Math.round(scaleX(mapping.brightnessStartX
                + brightnessRatio * (mapping.brightnessEndX - mapping.brightnessStartX),
                metrics.widthPixels, mapping.brightnessWidth));
        int brightnessY = Math.round(scaleY(mapping.brightnessStartY
                + brightnessRatio * (mapping.brightnessEndY - mapping.brightnessStartY),
                metrics.heightPixels, mapping.brightnessHeight));

        removeFloatingView();
        handler.postDelayed(() -> {
            if (!dispatchTap(colourX, colourY)) {
                toast("色盘手势未被系统接受。 ");
                showBubble();
                return;
            }
            handler.postDelayed(() -> {
                boolean brightnessSent = dispatchTap(brightnessX, brightnessY);
                toast(brightnessSent ? "已应用手动 RGB 与亮度。" : "已点击色盘，但亮度手势未被系统接受。 ");
                showBubble();
            }, 250);
        }, 120);
    }

    private boolean hasMatchingAspect(DisplayMetrics metrics, int referenceWidth, int referenceHeight) {
        float currentAspect = metrics.widthPixels / (float) metrics.heightPixels;
        float referenceAspect = referenceWidth / (float) referenceHeight;
        return Math.abs(currentAspect - referenceAspect) <= 0.01f;
    }

    private float scaleX(float x, int currentWidth, int referenceWidth) {
        return x * currentWidth / referenceWidth;
    }

    private float scaleY(float y, int currentHeight, int referenceHeight) {
        return y * currentHeight / referenceHeight;
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
        CharSequence text = node.getText();
        CharSequence description = node.getContentDescription();
        if (containsColour(text) || containsColour(description)) {
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
        return value.contains("颜色") || value.contains("顏色")
                || value.contains("色温") || value.contains("色溫")
                || value.toLowerCase().contains("color");
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

    private void toast(String message) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show();
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
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
                        showPalette();
                    }
                    return true;
                default:
                    return true;
            }
        }
    }
}
