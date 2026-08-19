package com.example.yeelightrgb;

import android.content.Context;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** Persists calibration points locally; no screenshots or account details are retained. */
final class PresetStore {
    private static final String PREFERENCES = "mijia_colour_tap";
    private static final String KEY_PRESETS = "presets";
    private static final String KEY_MANUAL_COLOUR = "manual_colour";
    private static final String KEY_MAPPING = "mapping";

    private PresetStore() { }

    static List<Preset> load(Context context) {
        ArrayList<Preset> result = new ArrayList<>();
        String serialized = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
                .getString(KEY_PRESETS, "[]");
        try {
            JSONArray array = new JSONArray(serialized);
            for (int i = 0; i < array.length(); i++) {
                JSONObject item = array.getJSONObject(i);
                result.add(new Preset(item.getString("name"), item.getInt("x"), item.getInt("y"),
                        item.getInt("width"), item.getInt("height"), item.getInt("previewColor")));
            }
        } catch (JSONException ignored) {
            // A corrupt local preference must not block the assistant.
        }
        return result;
    }

    static void add(Context context, Preset preset) {
        List<Preset> presets = load(context);
        presets.add(preset);
        save(context, presets);
    }

    static void removeAt(Context context, int index) {
        List<Preset> presets = load(context);
        if (index >= 0 && index < presets.size()) {
            presets.remove(index);
            save(context, presets);
        }
    }

    static ManualColour loadManualColour(Context context) {
        String serialized = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
                .getString(KEY_MANUAL_COLOUR, "");
        try {
            JSONObject value = new JSONObject(serialized);
            return new ManualColour(value.getInt("red"), value.getInt("green"), value.getInt("blue"),
                    value.getInt("brightness"));
        } catch (JSONException ignored) {
            return new ManualColour(255, 0, 0, 100);
        }
    }

    static void saveManualColour(Context context, ManualColour colour) {
        try {
            JSONObject value = new JSONObject();
            value.put("red", colour.red);
            value.put("green", colour.green);
            value.put("blue", colour.blue);
            value.put("brightness", colour.brightness);
            context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit()
                    .putString(KEY_MANUAL_COLOUR, value.toString()).apply();
        } catch (JSONException ignored) {
            // All values are integer values validated by the activity.
        }
    }

    static Mapping loadMapping(Context context) {
        String serialized = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
                .getString(KEY_MAPPING, "");
        try {
            JSONObject value = new JSONObject(serialized);
            return new Mapping(
                    value.optInt("colourWidth"), value.optInt("colourHeight"),
                    value.optInt("left"), value.optInt("top"), value.optInt("right"), value.optInt("bottom"),
                    value.optInt("brightnessWidth"), value.optInt("brightnessHeight"),
                    value.optInt("brightnessStartX"), value.optInt("brightnessStartY"),
                    value.optInt("brightnessEndX"), value.optInt("brightnessEndY")
            );
        } catch (JSONException ignored) {
            return new Mapping();
        }
    }

    static void saveColourBounds(Context context, int width, int height, int x1, int y1, int x2, int y2) {
        Mapping mapping = loadMapping(context);
        mapping.colourWidth = width;
        mapping.colourHeight = height;
        mapping.left = Math.min(x1, x2);
        mapping.top = Math.min(y1, y2);
        mapping.right = Math.max(x1, x2);
        mapping.bottom = Math.max(y1, y2);
        saveMapping(context, mapping);
    }

    static void saveBrightnessBounds(Context context, int width, int height, int x1, int y1, int x2, int y2) {
        Mapping mapping = loadMapping(context);
        mapping.brightnessWidth = width;
        mapping.brightnessHeight = height;
        mapping.brightnessStartX = x1;
        mapping.brightnessStartY = y1;
        mapping.brightnessEndX = x2;
        mapping.brightnessEndY = y2;
        saveMapping(context, mapping);
    }

    private static void saveMapping(Context context, Mapping mapping) {
        try {
            JSONObject value = new JSONObject();
            value.put("colourWidth", mapping.colourWidth);
            value.put("colourHeight", mapping.colourHeight);
            value.put("left", mapping.left);
            value.put("top", mapping.top);
            value.put("right", mapping.right);
            value.put("bottom", mapping.bottom);
            value.put("brightnessWidth", mapping.brightnessWidth);
            value.put("brightnessHeight", mapping.brightnessHeight);
            value.put("brightnessStartX", mapping.brightnessStartX);
            value.put("brightnessStartY", mapping.brightnessStartY);
            value.put("brightnessEndX", mapping.brightnessEndX);
            value.put("brightnessEndY", mapping.brightnessEndY);
            context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit()
                    .putString(KEY_MAPPING, value.toString()).apply();
        } catch (JSONException ignored) {
            // All values are internal integer calibration data.
        }
    }

    private static void save(Context context, List<Preset> presets) {
        JSONArray array = new JSONArray();
        for (Preset preset : presets) {
            try {
                JSONObject item = new JSONObject();
                item.put("name", preset.name);
                item.put("x", preset.x);
                item.put("y", preset.y);
                item.put("width", preset.referenceWidth);
                item.put("height", preset.referenceHeight);
                item.put("previewColor", preset.previewColor);
                array.put(item);
            } catch (JSONException ignored) {
                // All values are primitive values controlled by this application.
            }
        }
        context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
                .edit().putString(KEY_PRESETS, array.toString()).apply();
    }

    static final class Preset {
        final String name;
        final int x;
        final int y;
        final int referenceWidth;
        final int referenceHeight;
        final int previewColor;

        Preset(String name, int x, int y, int referenceWidth, int referenceHeight, int previewColor) {
            this.name = name;
            this.x = x;
            this.y = y;
            this.referenceWidth = referenceWidth;
            this.referenceHeight = referenceHeight;
            this.previewColor = previewColor;
        }
    }

    static final class ManualColour {
        final int red;
        final int green;
        final int blue;
        final int brightness;

        ManualColour(int red, int green, int blue, int brightness) {
            this.red = red;
            this.green = green;
            this.blue = blue;
            this.brightness = brightness;
        }

        int previewColour() {
            return android.graphics.Color.rgb(red, green, blue);
        }
    }

    static final class Mapping {
        int colourWidth;
        int colourHeight;
        int left;
        int top;
        int right;
        int bottom;
        int brightnessWidth;
        int brightnessHeight;
        int brightnessStartX;
        int brightnessStartY;
        int brightnessEndX;
        int brightnessEndY;

        Mapping() { }

        Mapping(int colourWidth, int colourHeight, int left, int top, int right, int bottom,
                int brightnessWidth, int brightnessHeight, int brightnessStartX, int brightnessStartY,
                int brightnessEndX, int brightnessEndY) {
            this.colourWidth = colourWidth;
            this.colourHeight = colourHeight;
            this.left = left;
            this.top = top;
            this.right = right;
            this.bottom = bottom;
            this.brightnessWidth = brightnessWidth;
            this.brightnessHeight = brightnessHeight;
            this.brightnessStartX = brightnessStartX;
            this.brightnessStartY = brightnessStartY;
            this.brightnessEndX = brightnessEndX;
            this.brightnessEndY = brightnessEndY;
        }

        boolean hasColourBounds() {
            return colourWidth > 0 && colourHeight > 0 && right > left && bottom > top;
        }

        boolean hasBrightnessBounds() {
            return brightnessWidth > 0 && brightnessHeight > 0
                    && (brightnessStartX != brightnessEndX || brightnessStartY != brightnessEndY);
        }
    }
}
