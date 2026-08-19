package com.example.yeelightrgb;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.util.List;

/** Entry point for calibrated Mi Home colour-picker taps. */
public final class MainActivity extends Activity {
    private static final int REQUEST_PICK_SCREENSHOT = 4101;
    private LinearLayout presetsContainer;
    private TextView statusView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(createContentView());
    }

    @Override
    protected void onResume() {
        super.onResume();
        renderPresets();
        statusView.setText(MijiaColorAccessibilityService.isReady()
                ? "状态：无障碍服务已开启。请在米家颜色页点击右侧“色卡”悬浮按钮。"
                : "状态：请先在系统设置中开启“米家色盘助手”无障碍服务。");
    }

    private View createContentView() {
        int padding = dp(18);
        ScrollView scrollView = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(padding, padding, padding, dp(28));
        scrollView.addView(root);

        root.addView(text("米家色盘助手", 26, true));
        TextView subtitle = text("校准一次色盘位置，之后用悬浮色卡重复点击同一位置。", 15, false);
        subtitle.setPadding(0, dp(4), 0, dp(12));
        root.addView(subtitle);

        statusView = text("", 14, false);
        statusView.setTextColor(Color.rgb(75, 75, 75));
        statusView.setPadding(0, 0, 0, dp(12));
        root.addView(statusView);

        Button accessibilityButton = button("打开无障碍设置");
        accessibilityButton.setOnClickListener(v -> startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        root.addView(accessibilityButton, matchWidth());

        Button miHomeButton = button("打开米家");
        miHomeButton.setOnClickListener(v -> openMiHome());
        root.addView(miHomeButton, matchWidth());

        root.addView(sectionTitle("新增色卡"));
        TextView guide = text("先在米家打开本灯的“颜色”色盘并截屏；回到这里选择该截图，再在截图上点选目标位置。截图只用于记录坐标，不会上传。", 14, false);
        guide.setTextColor(Color.rgb(80, 80, 80));
        root.addView(guide);
        Button calibrateButton = button("从米家截图校准色点");
        calibrateButton.setOnClickListener(v -> chooseScreenshot());
        root.addView(calibrateButton, matchWidth());

        root.addView(sectionTitle("已保存色卡"));
        presetsContainer = new LinearLayout(this);
        presetsContainer.setOrientation(LinearLayout.VERTICAL);
        root.addView(presetsContainer, matchWidth());

        TextView usage = text("使用：进入米家这盏灯的“颜色”页面 → 点击屏幕右侧的“色卡”悬浮按钮 → 选择预设。仅在米家颜色页且屏幕比例与校准截图一致时，助手才会点击。", 14, false);
        usage.setTextColor(Color.rgb(80, 80, 80));
        usage.setPadding(0, dp(18), 0, 0);
        root.addView(usage);
        return scrollView;
    }

    private void chooseScreenshot() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("image/*");
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        startActivityForResult(intent, REQUEST_PICK_SCREENSHOT);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQUEST_PICK_SCREENSHOT || resultCode != RESULT_OK || data == null) {
            return;
        }
        Uri imageUri = data.getData();
        if (imageUri == null) {
            return;
        }
        Intent calibrate = new Intent(this, CalibrationActivity.class);
        calibrate.setData(imageUri);
        calibrate.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        startActivity(calibrate);
    }

    private void openMiHome() {
        Intent launch = getPackageManager().getLaunchIntentForPackage(MijiaColorAccessibilityService.MI_HOME_PACKAGE);
        if (launch == null) {
            Toast.makeText(this, "未检测到米家 App。", Toast.LENGTH_SHORT).show();
            return;
        }
        startActivity(launch);
    }

    private void renderPresets() {
        if (presetsContainer == null) {
            return;
        }
        presetsContainer.removeAllViews();
        List<PresetStore.Preset> presets = PresetStore.load(this);
        if (presets.isEmpty()) {
            TextView empty = text("暂无色卡。", 14, false);
            empty.setTextColor(Color.GRAY);
            presetsContainer.addView(empty);
            return;
        }
        for (int index = 0; index < presets.size(); index++) {
            PresetStore.Preset preset = presets.get(index);
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setPadding(0, dp(4), 0, dp(4));

            View swatch = new View(this);
            GradientDrawable swatchBackground = new GradientDrawable();
            swatchBackground.setColor(preset.previewColor);
            swatchBackground.setCornerRadius(dp(6));
            swatch.setBackground(swatchBackground);
            LinearLayout.LayoutParams swatchParams = new LinearLayout.LayoutParams(dp(32), dp(32));
            swatchParams.rightMargin = dp(8);
            row.addView(swatch, swatchParams);

            TextView info = text(preset.name + "\n色盘点 (" + preset.x + ", " + preset.y + ")", 14, false);
            row.addView(info, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));

            Button delete = button("删除");
            final int deleteIndex = index;
            delete.setOnClickListener(v -> {
                PresetStore.removeAt(this, deleteIndex);
                renderPresets();
            });
            row.addView(delete);
            presetsContainer.addView(row, matchWidth());
        }
    }

    private TextView text(String value, int size, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        if (bold) {
            view.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        }
        return view;
    }

    private TextView sectionTitle(String value) {
        TextView title = text(value, 18, true);
        title.setPadding(0, dp(16), 0, dp(6));
        return title;
    }

    private Button button(String label) {
        Button button = new Button(this);
        button.setText(label);
        button.setAllCaps(false);
        return button;
    }

    private LinearLayout.LayoutParams matchWidth() {
        return new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }
}
