package org.apkrevival.tapquest;

import android.app.Activity;
import android.os.Bundle;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.util.Log;
import android.view.Gravity;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import org.json.JSONObject;

/** Self-authored fixture. No SDKs, proprietary assets, accounts or purchases. */
public class MainActivity extends Activity {
    private TextView status;
    private Button collect, retry;
    private SharedPreferences saves;
    private boolean offline, busy;
    private String endpoint;
    private int coins, level;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        saves = getSharedPreferences("tapquest", MODE_PRIVATE);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setGravity(Gravity.CENTER);
        layout.setPadding(30, 40, 30, 40);
        layout.setBackgroundColor(Color.rgb(16,23,34));
        TextView title = new TextView(this);
        title.setText("TAP QUEST"); title.setTextSize(32); title.setTextColor(Color.rgb(116,219,177));
        layout.addView(title);
        status = new TextView(this); status.setTextSize(22); status.setTextColor(Color.WHITE); status.setPadding(0,40,0,40); layout.addView(status);
        collect = new Button(this); collect.setText("Collect coin"); collect.setEnabled(false); layout.addView(collect);
        retry = new Button(this); retry.setText("Retry"); layout.addView(retry);
        TextView note = new TextView(this);note.setText("Self-authored server dependency fixture\nEvery 10 coins raises your level");note.setTextColor(Color.LTGRAY);layout.addView(note);
        setContentView(layout);
        collect.setOnClickListener(v -> { if (busy) return; if (offline) { coins++; level=1+coins/10; if (!saves.edit().putInt("coins",coins).putInt("level",level).commit()) { status.setText("Save failed"); return; } render("saved"); } else load(true); });
        retry.setOnClickListener(v -> { if (!busy) { if(offline) render("ready"); else load(false); } });
        try {
            JSONObject config = new JSONObject(read(getAssets().open("revival.json")));
            offline = config.getString("mode").equals("offline"); endpoint=config.getString("endpoint");
            if (offline) { coins=saves.getInt("coins",0);level=saves.getInt("level",1);render("ready"); }
            else load(false);
        } catch (Exception e) { status.setText("Config error: "+e); event("config_error"); }
    }
    private String read(InputStream in) throws Exception {
        try { ByteArrayOutputStream b = new ByteArrayOutputStream(); byte[] buf=new byte[4096]; int n; while((n=in.read(buf))!=-1)b.write(buf,0,n);return b.toString("UTF-8"); } finally {in.close();}
    }
    private void load(final boolean action) {
        busy=true;collect.setEnabled(false);retry.setEnabled(false);status.setText("Connecting...");
        new Thread(() -> {
            HttpURLConnection c=null;
            try {
                c=(HttpURLConnection)new URL(endpoint+(action?"/action":"/state")).openConnection();c.setConnectTimeout(3000);c.setReadTimeout(3000);
                if(action){c.setRequestMethod("POST");c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");byte[] body="{\"action\":\"collect\"}".getBytes("UTF-8");c.setFixedLengthStreamingMode(body.length);try(java.io.OutputStream out=c.getOutputStream()){out.write(body);} }
                JSONObject result=new JSONObject(read(c.getInputStream()));final int newCoins=result.getInt("coins"),newLevel=result.getInt("level");
                runOnUiThread(() -> {coins=newCoins;level=newLevel;busy=false;retry.setEnabled(true);render(action?"saved":"ready");});
            } catch(Exception e) {runOnUiThread(() -> {busy=false;collect.setEnabled(false);retry.setEnabled(true);status.setText("Backend unavailable. Start it and Retry.");event("backend_error");});}
            finally {if(c!=null)c.disconnect();}
        }).start();
    }
    private void render(String event) { status.setText("Coins: "+coins+"    Level: "+level);collect.setEnabled(true);event(event); }
    private void event(String name) {Log.i("APKRevival", "APKR_EVENT {\"event\":\""+name+"\",\"coins\":"+coins+",\"level\":"+level+",\"mode\":\""+(offline?"offline":"remote")+"\"}");}
}
