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
}
