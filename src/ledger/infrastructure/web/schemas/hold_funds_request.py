from decimal import Decimal, InvalidOperation

class HoldFundsRequestSchema:
    @staticmethod
    def validate(form_data: dict) -> dict:
        errors = []
        data = {}
        
        # Validate from_account_id
        try:
            data['from_account_id'] = int(form_data.get('from_account_id'))
        except (TypeError, ValueError):
            errors.append("Valid 'from_account_id' is required.")

        # Validate to_account_id
        try:
            data['to_account_id'] = int(form_data.get('to_account_id'))
        except (TypeError, ValueError):
            errors.append("Valid 'to_account_id' is required.")

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