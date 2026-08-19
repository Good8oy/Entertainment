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
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import android.text.InputType;

import java.util.List;

/** Entry point for calibrated Mi Home colour-picker taps. */
public final class MainActivity extends Activity {
    private static final int REQUEST_PICK_SCREENSHOT = 4101;
    private LinearLayout presetsContainer;
    private TextView statusView;
    private TextView mappingStatusView;
    private EditText redInput;
    private EditText greenInput;
    private EditText blueInput;
    private EditText brightnessInput;
    private int screenshotMode = CalibrationActivity.MODE_PRESET;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(createContentView());
    }

    @Override
    protected void onResume() {
        super.onResume();
        renderPresets();
        updateMappingStatus();
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

        root.addView(sectionTitle("手动 RGB 与亮度"));
        TextView manualGuide = text("RGB 用于计算色相与饱和度；亮度（1–100）对应已校准的米家亮度滑杆。保存后，到米家颜色页从悬浮色卡选择“应用手动 RGB”。", 14, false);
        manualGuide.setTextColor(Color.rgb(80, 80, 80));
        root.addView(manualGuide);
        PresetStore.ManualColour manualColour = PresetStore.loadManualColour(this);
        LinearLayout rgbRow = new LinearLayout(this);
        rgbRow.setOrientation(LinearLayout.HORIZONTAL);
        redInput = numberInput("R", manualColour.red);
        greenInput = numberInput("G", manualColour.green);
        blueInput = numberInput("B", manualColour.blue);
        rgbRow.addView(redInput, weighted());
        rgbRow.addView(greenInput, weighted());
        rgbRow.addView(blueInput, weighted());
        root.addView(rgbRow, matchWidth());
        brightnessInput = numberInput("亮度 1–100", manualColour.brightness);
        root.addView(brightnessInput, matchWidth());
        Button saveManualButton = button("保存手动 RGB 与亮度");
        saveManualButton.setOnClickListener(v -> saveManualColour());
        root.addView(saveManualButton, matchWidth());

        root.addView(sectionTitle("一次性坐标校准"));
        TextView mappingGuide = text("使用与实际操作相同的完整米家截图：色盘范围需点左上、右下；亮度滑杆需点 0%、100%。", 14, false);
        mappingGuide.setTextColor(Color.rgb(80, 80, 80));
        root.addView(mappingGuide);
        Button colourBoundsButton = button("校准 RGB 色盘范围");
        colourBoundsButton.setOnClickListener(v -> chooseScreenshot(CalibrationActivity.MODE_COLOUR_BOUNDS));
        root.addView(colourBoundsButton, matchWidth());
        Button brightnessBoundsButton = button("校准亮度滑杆");
        brightnessBoundsButton.setOnClickListener(v -> chooseScreenshot(CalibrationActivity.MODE_BRIGHTNESS_BOUNDS));
        root.addView(brightnessBoundsButton, matchWidth());
        mappingStatusView = text("", 14, false);
        mappingStatusView.setTextColor(Color.rgb(80, 80, 80));
        mappingStatusView.setPadding(0, dp(4), 0, 0);
        root.addView(mappingStatusView);

        root.addView(sectionTitle("新增色卡"));
        TextView guide = text("先在米家打开本灯的“颜色”色盘并截屏；回到这里选择该截图，再在截图上点选目标位置。截图只用于记录坐标，不会上传。", 14, false);
        guide.setTextColor(Color.rgb(80, 80, 80));
        root.addView(guide);
        Button calibrateButton = button("从米家截图校准色点");
        calibrateButton.setOnClickListener(v -> chooseScreenshot(CalibrationActivity.MODE_PRESET));
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

    private void chooseScreenshot(int mode) {
        screenshotMode = mode;
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
        calibrate.putExtra(CalibrationActivity.EXTRA_MODE, screenshotMode);
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

    private void saveManualColour() {
        Integer red = readInRange(redInput, "R", 0, 255);
        Integer green = readInRange(greenInput, "G", 0, 255);
        Integer blue = readInRange(blueInput, "B", 0, 255);
        Integer brightness = readInRange(brightnessInput, "亮度", 1, 100);
        if (red == null || green == null || blue == null || brightness == null) {
            return;
        }
        PresetStore.saveManualColour(this, new PresetStore.ManualColour(red, green, blue, brightness));
        Toast.makeText(this, "已保存；请回到米家颜色页，从悬浮色卡应用。", Toast.LENGTH_SHORT).show();
    }

    private Integer readInRange(EditText input, String label, int min, int max) {
        try {
            int value = Integer.parseInt(input.getText().toString().trim());
            if (value >= min && value <= max) {
                return value;
            }
        } catch (NumberFormatException ignored) {
        }
        Toast.makeText(this, label + " 必须在 " + min + " 到 " + max + " 之间。", Toast.LENGTH_SHORT).show();
        return null;
    }

    private void updateMappingStatus() {
        if (mappingStatusView == null) {
            return;
        }
        PresetStore.Mapping mapping = PresetStore.loadMapping(this);
        mappingStatusView.setText("校准状态：色盘" + (mapping.hasColourBounds() ? "已完成" : "未完成")
                + "；亮度滑杆" + (mapping.hasBrightnessBounds() ? "已完成" : "未完成"));
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

    private EditText numberInput(String hint, int value) {
        EditText input = new EditText(this);
        input.setHint(hint);
        input.setText(String.valueOf(value));
        input.setSingleLine(true);
        input.setGravity(Gravity.CENTER);
        input.setInputType(InputType.TYPE_CLASS_NUMBER);
        return input;
    }

    private LinearLayout.LayoutParams matchWidth() {
        return new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
    }

    private LinearLayout.LayoutParams weighted() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1);
        params.rightMargin = dp(4);
        return params;
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }
}
