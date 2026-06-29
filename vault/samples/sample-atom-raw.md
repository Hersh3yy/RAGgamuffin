# SAMPLE RAW NOTE — for smoke-testing the pipeline

> **Instructions**: Copy this file to `vault/01_unprocessed/sample-atom-raw.md`
> and run the `kb-process-note` playbook manually (Claw playbook section 6).
> A correctly functioning pipeline will produce `vault/02_wiki/sample-atom-raw.md`
> with YAML frontmatter, a `## Samenvatting` heading, at least one Mermaid diagram,
> and all code inside `<details>` toggles.
>
> This note is intentionally messy — that is the point.

---

the User model is the central identity record in the application. every person who can log in is a User.

fields: id, name, email, password, role
role can be one of: admin, manager, viewer

users authenticate with email + password. the system uses Laravel Sanctum for API tokens.
after login the token is returned and stored client side.

User.php has HasApiTokens and Notifiable traits.

```php
class User extends Authenticatable
{
    use HasApiTokens, Notifiable;

    protected $fillable = ['name', 'email', 'password', 'role'];

    public function hasRole(string $role): bool
    {
        return $this->role === $role;
    }

    public function isAdmin(): bool
    {
        return $this->role === 'admin';
    }
}
```

admins can do everything. managers can create and edit records. viewers are read-only.

the login flow: POST /api/login → validates credentials → returns sanctum token
the token is checked on every protected route via `auth:sanctum` middleware.

forgot i should mention: the system logs every login attempt to the audit_log table. success and failures both. the logging happens in the LoginController, not in the User model.

open question: what happens to active tokens when an admin manually resets a users password?
