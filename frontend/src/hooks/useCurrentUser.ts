import { useEffect, useState } from "react";
import client from "../api/client";
import type { User } from "../types/user";

export function useCurrentUser() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    client
      .get<User>("/users/me")
      .then((res) => {
        if (!cancelled) setUser(res.data);
      })
      .catch(() => {
        // fallback: show generic avatar
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { user, loading };
}
