from decimal import Decimal, InvalidOperation

class HoldFundsRequestSchema:
    @staticmethod
    def validate(form_data: dict) -> dict:
        errors = []
        data = {}
        
        # Validate from_account_id (UUID String)
        from_account_id = form_data.get('from_account_id')
        if not from_account_id:
            errors.append("Valid 'from_account_id' is required.")
        else:
            data['from_account_id'] = str(from_account_id)

        # Validate to_account_id (UUID String)
        to_account_id = form_data.get('to_account_id')
        if not to_account_id:
            errors.append("Valid 'to_account_id' is required.")
        else:
            data['to_account_id'] = str(to_account_id)

        # Validate amount
        amount_str = form_data.get('amount')
        try:
            amount = Decimal(str(amount_str))
            if amount <= 0:
                errors.append("Amount must be greater than zero.")
            data['amount'] = amount
        except (InvalidOperation, TypeError):
            errors.append("Valid numeric 'amount' is required.")

        # Validate optional fields safely
        merchant_id_str = form_data.get('merchant_id')
        data['merchant_id'] = int(merchant_id_str) if merchant_id_str else None
        data['user_email'] = form_data.get('user_email')

        if errors:
            raise ValueError(" | ".join(errors))
            
        return data