package linkedlist;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

public class DBHelper {

    public static Connection getConnection() {
        Connection conn = null;
        try {
            // 1. Load the Driver
            Class.forName("org.postgresql.Driver");

            // 2. Build Connection String
            // "jdbc:postgresql://<service-name>:<port>/<db-name>"
            String url = "jdbc:postgresql://" +
                         System.getenv("DB_HOST") + ":5432/" +
                         System.getenv("DB_NAME");

            // 3. Connect
            conn = DriverManager.getConnection(
                url,
                System.getenv("DB_USER"),
                System.getenv("DB_PASSWORD")
            );
            System.out.println("Connected to Postgres successfully.");

        } catch (Exception e) {
            System.out.println("DB Connection Error: " + e.getMessage());
            e.printStackTrace();
        }
        return conn;
    }
}