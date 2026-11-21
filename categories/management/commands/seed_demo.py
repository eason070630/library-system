from django.core.management.base import BaseCommand

from categories.models import Book, Category
from members.models import Member, MembershipType


class Command(BaseCommand):
    help = 'Load a few demo members, categories and books for testing/screenshots.'

    def handle(self, *args, **opts):
        from accounts.audit import suppressed
        with suppressed():
            self._load()
        self.stdout.write(self.style.SUCCESS('Demo data loaded.'))

    
    def _load(self):
    # 1. Create book categories
        category_data = {
            'Fiction': 'Novels and short stories',
            'Science': 'Science and scientific discoveries',
            'History': 'World and local history',
            'Fantasy': 'Fantasy and magical stories',
            'Mystery': 'Mystery and detective stories',
            'Romance': 'Romance novels',
            'Technology': 'Technology and computers',
            'Business': 'Business and management',
            'Education': 'Educational books',
            'Biography': 'Biographies and life stories',
        }

        category_objects = {}

        for category_name, description in category_data.items():
            category, created = Category.objects.get_or_create(
                name=category_name,
                defaults={'description': description}
            )

            category_objects[category_name] = category

    # 2. Add 50 demo books
        books = [
        # Fiction (1-10)
            ('The Great Gatsby', 'F. Scott Fitzgerald', 'Fiction'),
            ('To Kill a Mockingbird', 'Harper Lee', 'Fiction'),
            ('1984', 'George Orwell', 'Fiction'),
            ('Animal Farm', 'George Orwell', 'Fiction'),
            ('Pride and Prejudice', 'Jane Austen', 'Fiction'),
            ('Little Women', 'Louisa May Alcott', 'Fiction'),
            ('The Kite Runner', 'Khaled Hosseini', 'Fiction'),
            ('The Book Thief', 'Markus Zusak', 'Fiction'),
            ('The Alchemist', 'Paulo Coelho', 'Fiction'),
            ('The Catcher in the Rye', 'J. D. Salinger', 'Fiction'),

        # Fantasy (11-17)
            ('Harry Potter and the Philosophers Stone', 'J. K. Rowling', 'Fantasy'),
            ('Harry Potter and the Chamber of Secrets', 'J. K. Rowling', 'Fantasy'),
            ('The Hobbit', 'J. R. R. Tolkien', 'Fantasy'),
            ('The Fellowship of the Ring', 'J. R. R. Tolkien', 'Fantasy'),
            ('The Two Towers', 'J. R. R. Tolkien', 'Fantasy'),
            ('The Return of the King', 'J. R. R. Tolkien', 'Fantasy'),
            ('The Lion, the Witch and the Wardrobe', 'C. S. Lewis', 'Fantasy'),

        # Mystery (18-23)
            ('The Da Vinci Code', 'Dan Brown', 'Mystery'),
            ('Angels and Demons', 'Dan Brown', 'Mystery'),
            ('Murder on the Orient Express', 'Agatha Christie', 'Mystery'),
            ('And Then There Were None', 'Agatha Christie', 'Mystery'),
            ('The Hound of the Baskervilles', 'Arthur Conan Doyle', 'Mystery'),
            ('Gone Girl', 'Gillian Flynn', 'Mystery'),

        # Romance (24-28)
            ('Me Before You', 'Jojo Moyes', 'Romance'),
            ('The Notebook', 'Nicholas Sparks', 'Romance'),
            ('P.S. I Love You', 'Cecelia Ahern', 'Romance'),
            ('The Fault in Our Stars', 'John Green', 'Romance'),
            ('Five Feet Apart', 'Rachael Lippincott', 'Romance'),

        # Science (29-33)
            ('A Brief History of Time', 'Stephen Hawking', 'Science'),
            ('The Selfish Gene', 'Richard Dawkins', 'Science'),
            ('Cosmos', 'Carl Sagan', 'Science'),
            ('The Origin of Species', 'Charles Darwin', 'Science'),
            ('The Gene', 'Siddhartha Mukherjee', 'Science'),

        # Technology (34-38)
            ('Clean Code', 'Robert C. Martin', 'Technology'),
            ('The Pragmatic Programmer', 'Andrew Hunt', 'Technology'),
            ('Code', 'Charles Petzold', 'Technology'),
            ('The Innovators', 'Walter Isaacson', 'Technology'),
            ('Introduction to Algorithms', 'Thomas H. Cormen', 'Technology'),

        # Business (39-43)
            ('Rich Dad Poor Dad', 'Robert Kiyosaki', 'Business'),
            ('The Lean Startup', 'Eric Ries', 'Business'),
            ('Think and Grow Rich', 'Napoleon Hill', 'Business'),
            ('The 7 Habits of Highly Effective People', 'Stephen Covey', 'Business'),
            ('Atomic Habits', 'James Clear', 'Business'),

        # Education (44-47)
            ('Mindset', 'Carol S. Dweck', 'Education'),
            ('Deep Work', 'Cal Newport', 'Education'),
            ('Make It Stick', 'Peter C. Brown', 'Education'),
            ('The Power of Habit', 'Charles Duhigg', 'Education'),

        # Biography (48-50)
            ('Steve Jobs', 'Walter Isaacson', 'Biography'),
            ('Long Walk to Freedom', 'Nelson Mandela', 'Biography'),
            ('Wings of Fire', 'A. P. J. Abdul Kalam', 'Biography'),
        ]

    # Preserve ISBNs of the three books from your original seed data.
        known_isbns = {
            'The Great Gatsby': '9780743273565',
            'A Brief History of Time': '9780553380163',
            'Sapiens': '9780062316097',
        }

        added = 0

        for index, (title, author, category_name) in enumerate(books, start=1):
            isbn = known_isbns.get(title, f'9780000000{index:03d}')

            book, created = Book.objects.get_or_create(
                isbn=isbn,
                defaults={
                    'title': title,
                    'author': author,
                    'category': category_objects[category_name],
                }
            )

        # Update category for existing demo books too.
            if not created and book.category_id is None:
                book.category = category_objects[category_name]
                book.save(update_fields=['category'])

            if created:
                added += 1

        self.stdout.write(
            self.style.SUCCESS(f'{added} new demo books added.')
        )

    # 3. Keep original demo members
        tiers = {t.name: t for t in MembershipType.objects.all()}

        for name, email, phone, tier in [
            ('Alice Tan', 'alice@example.com', '0123456789', 'Gold'),
            ('Brian Lim', 'brian@example.com', '0129876543', 'Silver'),
            ('Chloe Wong', 'chloe@example.com', '0111234567', 'Basic')
        ]:
            if tier not in tiers:
                self.stdout.write(
                    self.style.WARNING(f'Membership type {tier} not found. Skipping {name}.')
                )
                continue

            Member.objects.get_or_create(
                email=email,
                defaults={
                    'name': name,
                    'phone': phone,
                    'membership_type': tiers[tier]
                }
            )

    # 4. Keep original demo accounts and appointments
        self._seed_accounts_and_appointments()


    def _seed_accounts_and_appointments(self):
        from datetime import date, time, timedelta

        from django.contrib.auth import get_user_model

        from accounts.models import Role, UserProfile
        from appointments.models import Appointment, TimeSlot

        User = get_user_model()
        for username, name, role, pw in [
                ('admin', 'Demo Admin', 'Administrator', 'Admin@12345'),
                ('librarian', 'Demo Librarian', 'Librarian', 'Library@12345'),
                ('assistant', 'Demo Assistant', 'Assistant', 'Assist@12345')]:
            if not User.objects.filter(username=username).exists():
                u = User.objects.create_user(username, f'{username}@example.com', pw, first_name=name)
                UserProfile.objects.create(user=u, role=Role.objects.get(name=role))
                self.stdout.write(f'  demo account: {username} / {pw}')
        today = date.today()
        for d in (1, 2, 3):
            for h in (9, 10, 14):
                TimeSlot.objects.get_or_create(
                    date=today + timedelta(days=d), start_time=time(h, 0),
                    defaults={'end_time': time(h + 1, 0), 'capacity': 3})
        slot = TimeSlot.objects.order_by('date', 'start_time').filter(date__gt=today).first()
        alice = Member.objects.filter(email='alice@example.com').first()
        if slot and alice and not Appointment.objects.exists():
            Appointment.objects.create(member=alice, slot=slot, purpose=Appointment.CONSULT, note='Demo appointment')
