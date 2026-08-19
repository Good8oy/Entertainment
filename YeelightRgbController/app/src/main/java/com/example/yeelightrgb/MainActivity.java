package com.example.yeelightrgb;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

/** Configures a live RGB target and one safe Mi Home colour-plane search region. */
public final class MainActivity extends Activity {
    private static final int REQUEST_PICK_SCREENSHOT = 4101;
    private EditText redInput;
    private EditText greenInput;
    private EditText blueInput;
    private TextView statusView;
    private TextView regionStatusView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(createContentView());
    }

    @Override
    protected void onResume() {
        super.onResume();
        statusView.setText(MijiaColorAccessibilityService.isReady()
                ? "状态：无障碍服务已开启。请在米家颜色页点击右侧“找色”悬浮按钮。"
                : "状态：请先在系统设置中开启“米家色盘助手”无障碍服务。");
        updateRegionStatus();
    }

    private View createContentView() {
        int padding = dp(18);
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(padding, padding, padding, dp(28));
        scroll.addView(root);

        root.addView(text("米家 RGB 找色助手", 26, true));
        TextView subtitle = text("实时识别米家屏幕中的目标 RGB，只在校准的色盘区域内点击。", 15, false);
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

        root.addView(sectionTitle("目标 RGB"));
        TextView targetGuide = text("输入要在米家色盘上寻找的 RGB（每项 0–255）。找色时会截取当前屏幕，但只扫描下方已校准的色盘矩形。", 14, false);
        targetGuide.setTextColor(Color.rgb(80, 80, 80));
        root.addView(targetGuide);
        PresetStore.RgbTarget target = PresetStore.loadTarget(this);
        LinearLayout rgbRow = new LinearLayout(this);
        rgbRow.setOrientation(LinearLayout.HORIZONTAL);
        redInput = numberInput("R", target.red);
        greenInput = numberInput("G", target.green);
        blueInput = numberInput("B", target.blue);
        rgbRow.addView(redInput, weighted());
        rgbRow.addView(greenInput, weighted());
        rgbRow.addView(blueInput, weighted());
        root.addView(rgbRow, matchWidth());
        Button saveTargetButton = button("保存目标 RGB");
        saveTargetButton.setOnClickListener(v -> saveTarget());
        root.addView(saveTargetButton, matchWidth());

        root.addView(sectionTitle("安全点击区域"));
        TextView regionGuide = text("在米家颜色页截取完整屏幕图，再在截图上依次点彩色色盘矩形的左上角和右下角。运行时扫描和模拟点击都会严格限制在此区域内。", 14, false);
        regionGuide.setTextColor(Color.rgb(80, 80, 80));
        root.addView(regionGuide);
        Button calibrateButton = button("从米家截图校准色盘区域");
        calibrateButton.setOnClickListener(v -> chooseScreenshot());
        root.addView(calibrateButton, matchWidth());
        regionStatusView = text("", 14, false);
        regionStatusView.setTextColor(Color.rgb(80, 80, 80));
        regionStatusView.setPadding(0, dp(4), 0, 0);
        root.addView(regionStatusView);

        TextView useGuide = text("使用：保存 RGB → 手动打开米家中本灯的颜色页 → 点击“找色”悬浮按钮 → 选择“识别并点击目标 RGB”。若在安全区域中未找到足够接近的像素，程序会停止且不会点击。", 14, false);
        useGuide.setTextColor(Color.rgb(80, 80, 80));
        useGuide.setPadding(0, dp(18), 0, 0);
        root.addView(useGuide);
        return scroll;
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

    private void saveTarget() {
        Integer red = readByte(redInput, "R");
        Integer green = readByte(greenInput, "G");
        Integer blue = readByte(blueInput, "B");
        if (red == null || green == null || blue == null) {
            return;
        }
        PresetStore.saveTarget(this, new PresetStore.RgbTarget(red, green, blue));
        Toast.makeText(this, "目标 RGB 已保存。", Toast.LENGTH_SHORT).show();
    }

    private Integer readByte(EditText input, String label) {
        try {
            int value = Integer.parseInt(input.getText().toString().trim());
            if (value >= 0 && value <= 255) {
                return value;
            }
        } catch (NumberFormatException ignored) {
        }
        Toast.makeText(this, label + " 必须在 0 到 255 之间。", Toast.LENGTH_SHORT).show();
        return null;
    }

    private void updateRegionStatus() {
        if (regionStatusView == null) {
            return;
        }
        PresetStore.ColourRegion region = PresetStore.loadRegion(this);
        regionStatusView.setText(region.isValid()
                ? "校准状态：已完成。区域 (" + region.left + ", " + region.top + ") 到 ("
                + region.right + ", " + region.bottom + ")。"
                : "校准状态：未完成。 ");
    }

    private void openMiHome() {
        Intent launch = getPackageManager().getLaunchIntentForPackage(MijiaColorAccessibilityService.MI_HOME_PACKAGE);
        if (launch == null) {
            Toast.makeText(this, "未检测到米家 App，请手动打开。", Toast.LENGTH_SHORT).show();
            return;
        }
        startActivity(launch);
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
