package com.example.yeelightrgb;

import android.app.Activity;
import android.app.AlertDialog;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.ImageDecoder;
import android.graphics.Matrix;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.io.IOException;
import java.io.InputStream;

/** Translates a point in a full-screen Mi Home screenshot into a screen coordinate. */
public final class CalibrationActivity extends Activity {
    static final String EXTRA_MODE = "mode";
    static final int MODE_PRESET = 0;
    static final int MODE_COLOUR_BOUNDS = 1;
    static final int MODE_BRIGHTNESS_BOUNDS = 2;

    private Bitmap screenshot;
    private ImageView imageView;
    private TextView statusView;
    private int mode;
    private int firstX = -1;
    private int firstY = -1;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        mode = getIntent().getIntExtra(EXTRA_MODE, MODE_PRESET);
        setContentView(createContentView());
        loadScreenshot(getIntent().getData());
    }

    @Override
    protected void onDestroy() {
        if (screenshot != null) {
            screenshot.recycle();
        }
        super.onDestroy();
    }

    private View createContentView() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(16), dp(16), dp(16), dp(30));
        scroll.addView(root);

        TextView title = new TextView(this);
        title.setText(mode == MODE_PRESET ? "点选米家色盘位置" : "校准米家控制区域");
        title.setTextSize(22);
        title.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        root.addView(title);

        TextView guide = new TextView(this);
        guide.setText(guideText());
        guide.setTextSize(14);
        guide.setPadding(0, dp(6), 0, dp(8));
        root.addView(guide);

        statusView = new TextView(this);
        statusView.setTextSize(14);
        statusView.setTextColor(Color.DKGRAY);
        root.addView(statusView);

        imageView = new ImageView(this);
        imageView.setAdjustViewBounds(true);
        imageView.setScaleType(ImageView.ScaleType.FIT_CENTER);
        imageView.setOnTouchListener(this::onScreenshotTouch);
        root.addView(imageView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        ));
        return scroll;
    }

    private void loadScreenshot(Uri uri) {
        if (uri == null) {
            statusView.setText("没有收到截图。 ");
            return;
        }
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                screenshot = ImageDecoder.decodeBitmap(
                        ImageDecoder.createSource(getContentResolver(), uri),
                        (decoder, info, source) -> decoder.setAllocator(ImageDecoder.ALLOCATOR_SOFTWARE)
                ).copy(Bitmap.Config.ARGB_8888, false);
            } else {
                try (InputStream input = getContentResolver().openInputStream(uri)) {
                    screenshot = BitmapFactory.decodeStream(input);
                }
            }
            if (screenshot == null) {
                statusView.setText("无法读取该截图。 ");
                return;
            }
            imageView.setImageBitmap(screenshot);
            statusView.setText("截图分辨率：" + screenshot.getWidth() + " × " + screenshot.getHeight());
        } catch (IOException | RuntimeException e) {
            statusView.setText("读取截图失败：" + e.getMessage());
        }
    }

    private boolean onScreenshotTouch(View view, MotionEvent event) {
        if (screenshot == null || event.getAction() != MotionEvent.ACTION_UP) {
            return true;
        }
        Matrix inverse = new Matrix();
        if (!imageView.getImageMatrix().invert(inverse)) {
            statusView.setText("坐标换算失败。 ");
            return true;
        }
        float[] point = new float[]{event.getX(), event.getY()};
        inverse.mapPoints(point);
        int x = Math.round(point[0]);
        int y = Math.round(point[1]);
        if (x < 0 || y < 0 || x >= screenshot.getWidth() || y >= screenshot.getHeight()) {
            statusView.setText("请点击截图内容区域。 ");
            return true;
        }
        if (mode == MODE_PRESET) {
            promptToSave(x, y, screenshot.getPixel(x, y));
        } else {
            saveCalibrationPoint(x, y);
        }
        return true;
    }

    private String guideText() {
        if (mode == MODE_COLOUR_BOUNDS) {
            return "先点色盘矩形的左上角，再点右下角。请只选取实际可点的彩色区域。";
        }
        if (mode == MODE_BRIGHTNESS_BOUNDS) {
            return "先点亮度滑杆的 0% 位置，再点 100% 位置。两点可为水平或垂直方向。";
        }
        return "请精确点击截图中色盘上的目标颜色。不要点击“我的模式”色块；随后为该点命名。";
    }

    private void saveCalibrationPoint(int x, int y) {
        if (firstX < 0) {
            firstX = x;
            firstY = y;
            statusView.setText(mode == MODE_COLOUR_BOUNDS
                    ? "已记录第一个点；请点色盘矩形的右下角。"
                    : "已记录 0% 位置；请点亮度滑杆的 100% 位置。");
            return;
        }
        if (mode == MODE_COLOUR_BOUNDS) {
            PresetStore.saveColourBounds(this, screenshot.getWidth(), screenshot.getHeight(), firstX, firstY, x, y);
            statusView.setText("色盘范围已保存。 ");
        } else {
            PresetStore.saveBrightnessBounds(this, screenshot.getWidth(), screenshot.getHeight(), firstX, firstY, x, y);
            statusView.setText("亮度滑杆范围已保存。 ");
        }
        finish();
    }

    private void promptToSave(int x, int y, int colour) {
        EditText nameInput = new EditText(this);
        nameInput.setHint("例如：拍摄青色");
        new AlertDialog.Builder(this)
                .setTitle("保存色盘点")
                .setMessage("坐标 (" + x + ", " + y + ")")
                .setView(nameInput)
                .setNegativeButton("取消", null)
                .setPositiveButton("保存", (dialog, which) -> {
                    String name = nameInput.getText().toString().trim();
                    if (name.isEmpty()) {
                        name = "未命名色卡";
                    }
                    PresetStore.add(this, new PresetStore.Preset(name, x, y,
                            screenshot.getWidth(), screenshot.getHeight(), colour));
                    finish();
                })
                .show();
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }
}
