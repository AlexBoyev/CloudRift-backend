package linkedlist;

import com.sun.net.httpserver.HttpServer;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpExchange;
import java.io.IOException;
import java.io.OutputStream;
import java.io.OutputStreamWriter;
import java.io.InputStream;
import java.net.InetSocketAddress;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.Statement;
import java.nio.charset.StandardCharsets;

// --- PROMETHEUS IMPORTS ---
import io.prometheus.client.CollectorRegistry;
import io.prometheus.client.exporter.common.TextFormat;
import io.prometheus.client.hotspot.DefaultExports;

public class LinkedListService {

    public static void main(String[] args) throws IOException {
        // 1. Initialize Default Metrics (CPU, Memory, Garbage Collection)
        DefaultExports.initialize();

        // Create HTTP Server on Port 8080
        HttpServer server = HttpServer.create(new InetSocketAddress(8080), 0);

        // --- Define Routes ---
        server.createContext("/list", new ListHandler());
        server.createContext("/add", new AddHandler());
        server.createContext("/delete", new RemoveTailHandler());
        server.createContext("/remove-head", new RemoveHeadHandler());
        server.createContext("/health", new HealthHandler());

        // 2. Add Metrics Endpoint
        server.createContext("/metrics", new MetricsHandler());

        server.setExecutor(null);
        System.out.println("Java LinkedList Service running on port 8080");
        server.start();
    }

    // --- PROMETHEUS HANDLER ---
    static class MetricsHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange t) throws IOException {
            // Tell Grafana this is text format 004
            t.getResponseHeaders().set("Content-Type", TextFormat.CONTENT_TYPE_004);
            t.sendResponseHeaders(200, 0);

            // Write the metrics from the registry to the response
            try (OutputStreamWriter writer = new OutputStreamWriter(t.getResponseBody())) {
                TextFormat.write004(writer, CollectorRegistry.defaultRegistry.metricFamilySamples());
            }
        }
    }

    // --- EXISTING HANDLERS BELOW (Keep them exactly as they were) ---

    static class ListHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange t) throws IOException {
            StringBuilder json = new StringBuilder("[");
            try (Connection conn = DBHelper.getConnection();
                 Statement stmt = conn.createStatement();
                 ResultSet rs = stmt.executeQuery("SELECT value FROM linked_list ORDER BY id ASC")) {
                boolean first = true;
                while (rs.next()) {
                    if (!first) json.append(",");
                    json.append("\"").append(rs.getString("value")).append("\"");
                    first = false;
                }
            } catch (Exception e) {
                e.printStackTrace();
            }
            json.append("]");
            sendResponse(t, 200, json.toString());
        }
    }

    static class AddHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange t) throws IOException {
            if ("POST".equals(t.getRequestMethod())) {
                InputStream is = t.getRequestBody();
                String body = new String(is.readAllBytes(), StandardCharsets.UTF_8);
                String value = body.replace("{\"value\":\"", "").replace("\"}", "").replace("\"", "").trim();
                try (Connection conn = DBHelper.getConnection();
                     PreparedStatement pstmt = conn.prepareStatement("INSERT INTO linked_list (value) VALUES (?)")) {
                    pstmt.setString(1, value);
                    pstmt.executeUpdate();
                    sendResponse(t, 200, "{\"status\": \"added\", \"value\": \"" + value + "\"}");
                } catch (Exception e) {
                    e.printStackTrace();
                    sendResponse(t, 500, "{\"error\": \"DB Error\"}");
                }
            } else {
                sendResponse(t, 405, "Method Not Allowed");
            }
        }
    }

    static class RemoveTailHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange t) throws IOException {
            if ("POST".equals(t.getRequestMethod())) {
                try (Connection conn = DBHelper.getConnection();
                     Statement stmt = conn.createStatement()) {
                    String sql = "DELETE FROM linked_list WHERE id = (SELECT id FROM linked_list ORDER BY id DESC LIMIT 1)";
                    int rowsAffected = stmt.executeUpdate(sql);
                    if (rowsAffected > 0) {
                        sendResponse(t, 200, "{\"status\": \"removed tail\"}");
                    } else {
                        sendResponse(t, 200, "{\"status\": \"list empty\"}");
                    }
                } catch (Exception e) {
                    e.printStackTrace();
                    sendResponse(t, 500, "{\"error\": \"DB Error\"}");
                }
            } else {
                sendResponse(t, 405, "Method Not Allowed");
            }
        }
    }

    static class RemoveHeadHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange t) throws IOException {
            if ("POST".equals(t.getRequestMethod())) {
                try (Connection conn = DBHelper.getConnection();
                     Statement stmt = conn.createStatement()) {
                    String sql = "DELETE FROM linked_list WHERE id = (SELECT id FROM linked_list ORDER BY id ASC LIMIT 1)";
                    int rowsAffected = stmt.executeUpdate(sql);
                    if (rowsAffected > 0) {
                        sendResponse(t, 200, "{\"status\": \"removed head\"}");
                    } else {
                        sendResponse(t, 200, "{\"status\": \"list empty\"}");
                    }
                } catch (Exception e) {
                    e.printStackTrace();
                    sendResponse(t, 500, "{\"error\": \"DB Error\"}");
                }
            } else {
                sendResponse(t, 405, "Method Not Allowed");
            }
        }
    }

    static class HealthHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange t) throws IOException {
            sendResponse(t, 200, "OK");
        }
    }

    private static void sendResponse(HttpExchange t, int statusCode, String response) throws IOException {
        t.getResponseHeaders().set("Content-Type", "application/json");
        t.sendResponseHeaders(statusCode, response.length());
        OutputStream os = t.getResponseBody();
        os.write(response.getBytes());
        os.close();
    }
}