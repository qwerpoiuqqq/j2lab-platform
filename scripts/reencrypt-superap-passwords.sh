#!/usr/bin/env bash
# Re-encrypt superap account passwords with new secret key
set -euo pipefail

if [ -z "${OLD_SECRET_KEY:-}" ] || [ -z "${NEW_SECRET_KEY:-}" ]; then
    echo "Usage: OLD_SECRET_KEY=xxx NEW_SECRET_KEY=yyy ./scripts/reencrypt-superap-passwords.sh"
    exit 1
fi

echo "Re-encrypting superap passwords..."

docker compose exec -T api-server python -c "
import asyncio

async def reencrypt():
    from cryptography.fernet import Fernet
    import hashlib
    import base64
    from sqlalchemy import select
    from app.core.database import async_session_factory
    from app.models.superap_account import SuperapAccount

    def make_fernet(key: str) -> Fernet:
        dk = hashlib.sha256(key.encode()).digest()
        return Fernet(base64.urlsafe_b64encode(dk))

    old_f = make_fernet('${OLD_SECRET_KEY}')
    new_f = make_fernet('${NEW_SECRET_KEY}')

    async with async_session_factory() as session:
        result = await session.execute(select(SuperapAccount))
        accounts = list(result.scalars().all())
        count = 0
        for account in accounts:
            if not account.password_encrypted:
                continue
            try:
                plain = old_f.decrypt(account.password_encrypted.encode()).decode()
                account.password_encrypted = new_f.encrypt(plain.encode()).decode()
                count += 1
            except Exception as e:
                print(f'[WARN] Account {account.id} ({account.user_id_superap}): {e}')
        await session.commit()
        print(f'[OK] Re-encrypted {count}/{len(accounts)} accounts')

asyncio.run(reencrypt())
"
