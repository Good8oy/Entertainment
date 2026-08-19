package com.example.yeelightrgb;

import android.app.Activity;
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
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.io.IOException;
import java.io.InputStream;

/** Calibrates only the safe rectangle in which live RGB matching is allowed to tap. */
public final class CalibrationActivity extends Activity {
    private Bitmap screenshot;
    private ImageView imageView;
    private TextView statusView;
    private int firstX = -1;
    private int firstY = -1;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
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
        title.setText("校准安全色盘区域");
        title.setTextSize(22);
        title.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        root.addView(title);

        TextView guide = new TextView(this);
        guide.setText("先点米家彩色色盘矩形的左上角，再点右下角。运行时只会在此区域寻找 RGB，绝不会点击区域外的“模式”、定时或其他按钮。 ");
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
        if (firstX < 0) {
            firstX = x;
            firstY = y;
            statusView.setText("已记录左上角；请点色盘矩形的右下角。 ");
            return true;
        }
        PresetStore.saveRegion(this, screenshot.getWidth(), screenshot.getHeight(), firstX, firstY, x, y);
        statusView.setText("安全色盘区域已保存。 ");
        finish();
        return true;
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }
}
