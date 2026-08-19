package com.example.yeelightrgb;

import android.content.Context;

import org.json.JSONException;
import org.json.JSONObject;

/** Stores only the requested RGB target and the safe colour-plane search rectangle. */
final class PresetStore {
    private static final String PREFERENCES = "mijia_colour_tap";
    private static final String KEY_TARGET_RGB = "target_rgb";
    private static final String KEY_REGION = "colour_region";

    private PresetStore() { }

    static RgbTarget loadTarget(Context context) {
        String serialized = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
                .getString(KEY_TARGET_RGB, "");
        try {
            JSONObject value = new JSONObject(serialized);
            return new RgbTarget(value.getInt("red"), value.getInt("green"), value.getInt("blue"));
        } catch (JSONException ignored) {
            return new RgbTarget(255, 0, 0);
        }
    }

    static void saveTarget(Context context, RgbTarget target) {
        try {
            JSONObject value = new JSONObject();
            value.put("red", target.red);
            value.put("green", target.green);
            value.put("blue", target.blue);
            context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit()
                    .putString(KEY_TARGET_RGB, value.toString()).apply();
        } catch (JSONException ignored) {
            // Values are range-validated before being saved.
        }
    }

    static ColourRegion loadRegion(Context context) {
        String serialized = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
                .getString(KEY_REGION, "");
        try {
            JSONObject value = new JSONObject(serialized);
            return new ColourRegion(value.optInt("width"), value.optInt("height"),
                    value.optInt("left"), value.optInt("top"), value.optInt("right"), value.optInt("bottom"));
        } catch (JSONException ignored) {
            return new ColourRegion();
        }
    }

    static void saveRegion(Context context, int width, int height, int x1, int y1, int x2, int y2) {
        try {
            JSONObject value = new JSONObject();
            value.put("width", width);
            value.put("height", height);
            value.put("left", Math.min(x1, x2));
            value.put("top", Math.min(y1, y2));
            value.put("right", Math.max(x1, x2));
            value.put("bottom", Math.max(y1, y2));
            context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit()
                    .putString(KEY_REGION, value.toString()).apply();
        } catch (JSONException ignored) {
            // Values are internal screen coordinates.
        }
    }

    static final class RgbTarget {
        final int red;
        final int green;
        final int blue;

        RgbTarget(int red, int green, int blue) {
            this.red = red;
            this.green = green;
            this.blue = blue;
        }

        int previewColour() {
            return android.graphics.Color.rgb(red, green, blue);
        }
    }

    static final class ColourRegion {
        final int referenceWidth;
        final int referenceHeight;
        final int left;
        final int top;
        final int right;
        final int bottom;

        ColourRegion() {
            this(0, 0, 0, 0, 0, 0);
        }

        ColourRegion(int referenceWidth, int referenceHeight, int left, int top, int right, int bottom) {
            this.referenceWidth = referenceWidth;
            this.referenceHeight = referenceHeight;
            this.left = left;
            this.top = top;
            this.right = right;
            this.bottom = bottom;
        }

        boolean isValid() {
            return referenceWidth > 0 && referenceHeight > 0 && right > left && bottom > top;
        }
    }
}
