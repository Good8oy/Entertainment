package com.example.yeelightrgb;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.wifi.WifiManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** A compact local-network controller for Yeelight's documented TCP protocol. */
public final class MainActivity extends Activity {
    private static final String PREFERENCES = "yeelight_rgb_preferences";
    private static final String KEY_HOST = "host";
    private static final String KEY_PRESETS = "presets";

    private final ExecutorService networkExecutor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private EditText hostInput;
    private EditText redInput;
    private EditText greenInput;
    private EditText blueInput;
    private EditText brightnessInput;
    private TextView hexView;
    private View previewView;
    private TextView statusView;
    private LinearLayout presetsContainer;
    private SharedPreferences preferences;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        preferences = getSharedPreferences(PREFERENCES, MODE_PRIVATE);
        setContentView(createContentView());
        updatePreview();
        renderPresets();
    }

    @Override
    protected void onDestroy() {
        networkExecutor.shutdownNow();
        super.onDestroy();
    }

    private View createContentView() {
        int padding = dp(18);
        ScrollView scrollView = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(padding, padding, padding, dp(30));
        scrollView.addView(root);

        TextView title = text("Yeelight 精确色卡", 26, true);
        root.addView(title);
        TextView subtitle = text("直接发送固定 RGB 与亮度，不依赖色盘位置。", 15, false);
        subtitle.setPadding(0, dp(4), 0, dp(16));
        root.addView(subtitle);

        root.addView(sectionTitle("灯的局域网地址"));
        hostInput = editText("例如：192.168.1.35", InputType.TYPE_CLASS_TEXT);
        hostInput.setText(preferences.getString(KEY_HOST, ""));
        root.addView(hostInput, matchWidth());

        LinearLayout addressButtons = horizontal();
        Button discoverButton = button("搜索局域网灯");
        discoverButton.setOnClickListener(v -> discoverLights());
        addressButtons.addView(discoverButton, weight(1));
        Button testButton = button("测试连接");
        testButton.setOnClickListener(v -> testConnection());
        addressButtons.addView(testButton, weight(1));
        root.addView(addressButtons, matchWidth());

        TextView instructions = text("首次使用：在 Yeelight App 的设备页打开“局域网控制”，并确保手机与灯连在同一 Wi‑Fi。搜索不到时，可在路由器设备列表中找到灯的 IP 并手动填入。", 14, false);
        instructions.setTextColor(Color.rgb(80, 80, 80));
        instructions.setPadding(0, dp(4), 0, dp(18));
        root.addView(instructions);

        root.addView(sectionTitle("精确颜色"));
        LinearLayout rgbRow = horizontal();
        redInput = numberInput("R", "47");
        greenInput = numberInput("G", "111");
        blueInput = numberInput("B", "115");
        rgbRow.addView(redInput, weight(1));
        rgbRow.addView(greenInput, weight(1));
        rgbRow.addView(blueInput, weight(1));
        root.addView(rgbRow, matchWidth());

        brightnessInput = numberInput("亮度 1–100", "65");
        brightnessInput.setPadding(dp(10), 0, dp(10), 0);
        root.addView(brightnessInput, matchWidth());

        hexView = text("HEX：#2F6F73", 16, true);
        hexView.setPadding(0, dp(10), 0, dp(6));
        root.addView(hexView);
        previewView = new View(this);
        previewView.setContentDescription("当前 RGB 颜色预览");
        LinearLayout.LayoutParams previewParams = matchWidth();
        previewParams.height = dp(46);
        previewParams.bottomMargin = dp(12);
        root.addView(previewView, previewParams);

        TextWatcher watcher = new SimpleTextWatcher(this::updatePreview);
        redInput.addTextChangedListener(watcher);
        greenInput.addTextChangedListener(watcher);
        blueInput.addTextChangedListener(watcher);

        LinearLayout actionButtons = horizontal();
        Button applyButton = button("应用此颜色");
        applyButton.setOnClickListener(v -> applyCurrentColor());
        actionButtons.addView(applyButton, weight(1));
        Button addButton = button("保存为色卡");
        addButton.setOnClickListener(v -> promptSavePreset());
        actionButtons.addView(addButton, weight(1));
        root.addView(actionButtons, matchWidth());

        statusView = text("状态：等待操作", 14, false);
        statusView.setPadding(0, dp(10), 0, dp(8));
        root.addView(statusView);

        root.addView(sectionTitle("我的精确色卡"));
        presetsContainer = new LinearLayout(this);
        presetsContainer.setOrientation(LinearLayout.VERTICAL);
        root.addView(presetsContainer, matchWidth());
        return scrollView;
    }

    private void discoverLights() {
        setStatus("正在搜索局域网 Yeelight…");
        networkExecutor.execute(() -> {
            try {
                List<String> hosts = YeelightClient.discover(this);
                mainHandler.post(() -> showDiscoveredLights(hosts));
            } catch (IOException e) {
                mainHandler.post(() -> setStatus("搜索失败：" + friendlyMessage(e)));
            }
        });
    }

    private void showDiscoveredLights(List<String> hosts) {
        if (hosts.isEmpty()) {
            setStatus("未发现灯。请确认局域网控制已开启，并手动填写 IP 后测试连接。");
            return;
        }
        String[] choices = hosts.toArray(new String[0]);
        new AlertDialog.Builder(this)
                .setTitle("发现的 Yeelight")
                .setItems(choices, (dialog, which) -> {
                    hostInput.setText(choices[which]);
                    persistHost();
                    setStatus("已选设备：" + choices[which]);
                })
                .show();
    }

    private void testConnection() {
        String host = host();
        if (host == null) {
            return;
        }
        persistHost();
        setStatus("正在测试 " + host + "…");
        networkExecutor.execute(() -> {
            try {
                YeelightClient.getProperties(host);
                mainHandler.post(() -> setStatus("已连接到 " + host + "。"));
            } catch (IOException e) {
                mainHandler.post(() -> setStatus("无法连接：" + friendlyMessage(e)));
            }
        });
    }

    private void applyCurrentColor() {
        String host = host();
        ColorSettings color = readColorSettings();
        if (host == null || color == null) {
            return;
        }
        persistHost();
        setStatus("正在应用 " + color.toHex() + "，亮度 " + color.brightness + "%…");
        networkExecutor.execute(() -> {
            try {
                YeelightClient.applyColor(host, color);
                mainHandler.post(() -> setStatus("已应用 " + color.toHex() + "，亮度 " + color.brightness + "% 。"));
            } catch (IOException e) {
                mainHandler.post(() -> setStatus("设置失败：" + friendlyMessage(e)));
            }
        });
    }

    private void promptSavePreset() {
        ColorSettings color = readColorSettings();
        if (color == null) {
            return;
        }
        EditText nameInput = editText("例如：拍摄青色", InputType.TYPE_CLASS_TEXT);
        new AlertDialog.Builder(this)
                .setTitle("保存精确色卡")
                .setMessage(color.toHex() + "，亮度 " + color.brightness + "%")
                .setView(nameInput)
                .setNegativeButton("取消", null)
                .setPositiveButton("保存", (dialog, which) -> {
                    String name = nameInput.getText().toString().trim();
                    if (name.isEmpty()) {
                        name = "未命名色卡";
                    }
                    List<Preset> presets = loadPresets();
                    presets.add(new Preset(name, color));
                    savePresets(presets);
                    renderPresets();
                })
                .show();
    }

    private void renderPresets() {
        presetsContainer.removeAllViews();
        List<Preset> presets = loadPresets();
        if (presets.isEmpty()) {
            TextView empty = text("还没有色卡。设定 RGB 与亮度后，点击“保存为色卡”。", 14, false);
            empty.setTextColor(Color.GRAY);
            presetsContainer.addView(empty);
            return;
        }
        for (int index = 0; index < presets.size(); index++) {
            Preset preset = presets.get(index);
            LinearLayout row = horizontal();
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setPadding(0, dp(5), 0, dp(5));

            TextView swatch = text("", 1, false);
            GradientDrawable swatchBackground = new GradientDrawable();
            swatchBackground.setColor(preset.color.toAndroidColor());
            swatchBackground.setCornerRadius(dp(6));
            swatch.setBackground(swatchBackground);
            row.addView(swatch, fixed(dp(34), dp(34)));

            Button useButton = button(preset.name + "\n" + preset.color.toHex() + " · " + preset.color.brightness + "%");
            useButton.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
            useButton.setTextSize(14);
            useButton.setOnClickListener(v -> {
                fillColorInputs(preset.color);
                applyCurrentColor();
            });
            row.addView(useButton, weight(1));

            Button deleteButton = button("删除");
            deleteButton.setTextSize(12);
            final int deleteIndex = index;
            deleteButton.setOnClickListener(v -> {
                List<Preset> updated = loadPresets();
                if (deleteIndex < updated.size()) {
                    updated.remove(deleteIndex);
                    savePresets(updated);
                    renderPresets();
                }
            });
            row.addView(deleteButton, wrapWidth());
            presetsContainer.addView(row, matchWidth());
        }
    }

    private void fillColorInputs(ColorSettings color) {
        redInput.setText(String.valueOf(color.red));
        greenInput.setText(String.valueOf(color.green));
        blueInput.setText(String.valueOf(color.blue));
        brightnessInput.setText(String.valueOf(color.brightness));
        updatePreview();
    }

    private List<Preset> loadPresets() {
        List<Preset> presets = new ArrayList<>();
        String saved = preferences.getString(KEY_PRESETS, "[]");
        try {
            JSONArray array = new JSONArray(saved);
            for (int i = 0; i < array.length(); i++) {
                JSONObject object = array.getJSONObject(i);
                presets.add(new Preset(
                        object.getString("name"),
                        new ColorSettings(
                                object.getInt("red"),
                                object.getInt("green"),
                                object.getInt("blue"),
                                object.getInt("brightness")
                        )
                ));
            }
        } catch (JSONException ignored) {
            // Corrupt preference data should not prevent the controller from opening.
        }
        return presets;
    }

    private void savePresets(List<Preset> presets) {
        JSONArray array = new JSONArray();
        for (Preset preset : presets) {
            try {
                JSONObject object = new JSONObject();
                object.put("name", preset.name);
                object.put("red", preset.color.red);
                object.put("green", preset.color.green);
                object.put("blue", preset.color.blue);
                object.put("brightness", preset.color.brightness);
                array.put(object);
            } catch (JSONException ignored) {
                // JSONObject only receives values controlled by this application.
            }
        }
        preferences.edit().putString(KEY_PRESETS, array.toString()).apply();
    }

    private String host() {
        String host = hostInput.getText().toString().trim();
        if (host.isEmpty()) {
            toast("请先搜索或填写灯的 IP 地址。");
            return null;
        }
        return host;
    }

    private void persistHost() {
        preferences.edit().putString(KEY_HOST, hostInput.getText().toString().trim()).apply();
    }

    private ColorSettings readColorSettings() {
        try {
            int red = parseInRange(redInput, "R", 0, 255);
            int green = parseInRange(greenInput, "G", 0, 255);
            int blue = parseInRange(blueInput, "B", 0, 255);
            int brightness = parseInRange(brightnessInput, "亮度", 1, 100);
            return new ColorSettings(red, green, blue, brightness);
        } catch (IllegalArgumentException e) {
            toast(e.getMessage());
            return null;
        }
    }

    private int parseInRange(EditText input, String label, int minimum, int maximum) {
        String value = input.getText().toString().trim();
        try {
            int number = Integer.parseInt(value);
            if (number < minimum || number > maximum) {
                throw new IllegalArgumentException(label + " 必须在 " + minimum + " 到 " + maximum + " 之间。");
            }
            return number;
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException(label + " 请输入整数。");
        }
    }

    private void updatePreview() {
        if (previewView == null) {
            return;
        }
        try {
            int red = parseSilently(redInput, 0);
            int green = parseSilently(greenInput, 0);
            int blue = parseSilently(blueInput, 0);
            ColorSettings color = new ColorSettings(red, green, blue, 1);
            GradientDrawable background = new GradientDrawable();
            background.setColor(color.toAndroidColor());
            background.setCornerRadius(dp(8));
            previewView.setBackground(background);
            hexView.setText("HEX：" + color.toHex());
        } catch (RuntimeException ignored) {
            hexView.setText("HEX：请填写有效 RGB");
        }
    }

    private int parseSilently(EditText input, int fallback) {
        try {
            int value = Integer.parseInt(input.getText().toString().trim());
            return value >= 0 && value <= 255 ? value : fallback;
        } catch (NumberFormatException e) {
            return fallback;
        }
    }

    private void setStatus(String message) {
        statusView.setText("状态：" + message);
    }

    private void toast(String message) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show();
    }

    private String friendlyMessage(Exception error) {
        String message = error.getMessage();
        return message == null || message.isEmpty() ? error.getClass().getSimpleName() : message;
    }

    private TextView text(String value, int sizeSp, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(sizeSp);
        if (bold) {
            view.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        }
        return view;
    }

    private TextView sectionTitle(String value) {
        TextView view = text(value, 18, true);
        view.setPadding(0, dp(12), 0, dp(6));
        return view;
    }

    private EditText editText(String hint, int inputType) {
        EditText view = new EditText(this);
        view.setHint(hint);
        view.setTextSize(16);
        view.setSingleLine(true);
        view.setInputType(inputType);
        return view;
    }

    private EditText numberInput(String hint, String value) {
        EditText view = editText(hint, InputType.TYPE_CLASS_NUMBER);
        view.setText(value);
        view.setGravity(Gravity.CENTER);
        return view;
    }

    private Button button(String label) {
        Button view = new Button(this);
        view.setText(label);
        view.setAllCaps(false);
        return view;
    }

    private LinearLayout horizontal() {
        LinearLayout view = new LinearLayout(this);
        view.setOrientation(LinearLayout.HORIZONTAL);
        return view;
    }

    private LinearLayout.LayoutParams matchWidth() {
        return new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        );
    }

    private LinearLayout.LayoutParams wrapWidth() {
        return new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        );
    }

    private LinearLayout.LayoutParams fixed(int width, int height) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(width, height);
        params.rightMargin = dp(8);
        return params;
    }

    private LinearLayout.LayoutParams weight(int value) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, value);
        params.rightMargin = dp(4);
        return params;
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    private static final class Preset {
        final String name;
        final ColorSettings color;

        Preset(String name, ColorSettings color) {
            this.name = name;
            this.color = color;
        }
    }

    private static final class ColorSettings {
        final int red;
        final int green;
        final int blue;
        final int brightness;

        ColorSettings(int red, int green, int blue, int brightness) {
            this.red = red;
            this.green = green;
            this.blue = blue;
            this.brightness = brightness;
        }

        int toAndroidColor() {
            return Color.rgb(red, green, blue);
        }

        int toProtocolRgb() {
            return (red << 16) | (green << 8) | blue;
        }

        String toHex() {
            return String.format("#%02X%02X%02X", red, green, blue);
        }
    }

    private static final class SimpleTextWatcher implements TextWatcher {
        private final Runnable action;

        SimpleTextWatcher(Runnable action) {
            this.action = action;
        }

        @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) { }
        @Override public void onTextChanged(CharSequence s, int start, int before, int count) { action.run(); }
        @Override public void afterTextChanged(android.text.Editable s) { }
    }

    private static final class YeelightClient {
        private static final int PORT = 55443;
        private static final int DISCOVERY_PORT = 1982;
        private static final Pattern LOCATION = Pattern.compile(
                "(?im)^location:\\s*yeelight://([^:/\\s]+)(?::\\d+)?"
        );
        private static final String DISCOVER_MESSAGE = "M-SEARCH * HTTP/1.1\\r\\n"
                + "HOST: 239.255.255.250:1982\\r\\n"
                + "MAN: \\\"ssdp:discover\\\"\\r\\n"
                + "ST: wifi_bulb\\r\\n\\r\\n";

        static void applyColor(String host, ColorSettings color) throws IOException {
            try (Socket socket = connect(host)) {
                BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8));
                BufferedReader reader = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
                send(writer, reader, 1, "set_power", "[\\\"on\\\",\\\"sudden\\\",0]");
                send(writer, reader, 2, "set_rgb", "[" + color.toProtocolRgb() + ",\\\"sudden\\\",0]");
                send(writer, reader, 3, "set_bright", "[" + color.brightness + ",\\\"sudden\\\",0]");
            }
        }

        static void getProperties(String host) throws IOException {
            try (Socket socket = connect(host)) {
                BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8));
                BufferedReader reader = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
                send(writer, reader, 1, "get_prop", "[\\\"power\\\",\\\"rgb\\\",\\\"bright\\\"]");
            }
        }

        static List<String> discover(Context context) throws IOException {
            Set<String> hosts = new LinkedHashSet<>();
            WifiManager.MulticastLock multicastLock = null;
            WifiManager wifiManager = (WifiManager) context.getApplicationContext().getSystemService(Context.WIFI_SERVICE);
            if (wifiManager != null) {
                multicastLock = wifiManager.createMulticastLock("yeelight-discovery");
                multicastLock.setReferenceCounted(false);
                multicastLock.acquire();
            }
            try (DatagramSocket socket = new DatagramSocket()) {
                socket.setSoTimeout(500);
                byte[] request = DISCOVER_MESSAGE.getBytes(StandardCharsets.UTF_8);
                socket.send(new DatagramPacket(
                        request,
                        request.length,
                        InetAddress.getByName("239.255.255.250"),
                        DISCOVERY_PORT
                ));
                long endTime = System.currentTimeMillis() + 3000;
                byte[] responseBuffer = new byte[2048];
                while (System.currentTimeMillis() < endTime) {
                    try {
                        DatagramPacket response = new DatagramPacket(responseBuffer, responseBuffer.length);
                        socket.receive(response);
                        String data = new String(response.getData(), response.getOffset(), response.getLength(), StandardCharsets.UTF_8);
                        Matcher location = LOCATION.matcher(data);
                        if (location.find()) {
                            hosts.add(location.group(1));
                        }
                    } catch (java.net.SocketTimeoutException ignored) {
                        // Repeat until the three-second discovery window expires.
                    }
                }
            } finally {
                if (multicastLock != null && multicastLock.isHeld()) {
                    multicastLock.release();
                }
            }
            return new ArrayList<>(hosts);
        }

        private static Socket connect(String host) throws IOException {
            Socket socket = new Socket();
            socket.connect(new InetSocketAddress(host, PORT), 3000);
            socket.setSoTimeout(3000);
            return socket;
        }

        private static void send(BufferedWriter writer, BufferedReader reader, int id, String method, String params) throws IOException {
            writer.write("{\\\"id\\\":" + id + ",\\\"method\\\":\\\"" + method + "\\\",\\\"params\\\":" + params + "}\\r\\n");
            writer.flush();
            String response = reader.readLine();
            if (response == null) {
                throw new IOException("设备没有返回响应。");
            }
            if (response.contains("\\\"error\\\"")) {
                throw new IOException("设备拒绝命令：" + response);
            }
        }
    }
}
